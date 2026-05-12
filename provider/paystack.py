from typing import Optional, Any
from provider.base import BaseProvider
from model import PaymentResponse, ChargeRequest, PaymentStatus
from utils import to_minor_units, handle_http_errors, verify_paystack_signature
from core.config import logger

class PaystackProvider(BaseProvider):
    provider_name = "paystack"
    base_url = "https://api.paystack.co"

    async def initialize_payment(self, request: ChargeRequest) -> PaymentResponse:
        await super().initialize_payment(request)
        
        payload = {
            "email": request.email,
            "amount": to_minor_units(request.amount, request.currency),
            "currency": request.currency,
            "reference": request.reference,
            "callback_url": request.callback_url,
            "metadata": request.metadata,
        }

        logger.debug(f"[{self.provider_name}] Initializing transaction: {request.reference}")
        
        response = await self._request_with_retry(
            "POST",
            f"{self.base_url}/transaction/initialize",
            json={k: v for k, v in payload.items() if v is not None}
        )
        await handle_http_errors(response)
        
        data = response.json()["data"]
        return PaymentResponse(
            checkout_url=data["authorization_url"],
            reference=data["reference"],
            status=PaymentStatus.PENDING,
            amount=request.amount,
            currency=request.currency,
            provider=self.provider_name,
            provider_raw_response=response.json()
        )

    async def verify_payment(self, reference: str) -> PaymentResponse:
        await super().verify_payment(reference)
        
        response = await self._request_with_retry(
            "GET", 
            f"{self.base_url}/transaction/verify/{reference}"
        )
        await handle_http_errors(response)
        
        data = response.json()["data"]
        status_map = {
            "success": PaymentStatus.SUCCESSFUL,
            "failed": PaymentStatus.FAILED,
            "abandoned": PaymentStatus.CANCELLED,
            "reversed": PaymentStatus.REFUNDED,
            "processing": PaymentStatus.PROCESSING,
            "pending": PaymentStatus.PENDING,
        }
        
        return PaymentResponse(
            transaction_id=str(data["id"]),
            reference=data["reference"],
            status=status_map.get(data["status"], PaymentStatus.PROCESSING),
            amount=data["amount"] / 100.0,
            currency=data["currency"],
            provider=self.provider_name,
            message=data.get("gateway_response"),
            provider_raw_response=response.json()
        )

    async def refund(self, transaction_id: str, amount: Optional[float] = None, currency: Optional[str] = None) -> PaymentResponse:
        await super().refund(transaction_id, amount, currency)
        
        payload = {"transaction": transaction_id}
        if amount:
            payload["amount"] = to_minor_units(amount, currency or self.currency)

        response = await self._request_with_retry(
            "POST",
            f"{self.base_url}/refund", 
            json=payload
        )
        await handle_http_errors(response)
        
        data = response.json()["data"]
        return PaymentResponse(
            transaction_id=str(data["transaction"]["id"]),
            reference=data["transaction"]["reference"],
            status=PaymentStatus.REFUNDED,
            amount=data["amount"] / 100.0,
            currency=data["currency"],
            provider=self.provider_name,
            provider_raw_response=response.json()
        )

    def validate_webhook(self, payload: dict[str, Any], signature: str) -> bool:
        super().validate_webhook(payload, signature)
        return verify_paystack_signature(self.secret_key, payload, signature)
    return verify_paystack_signature(self.secret_key, payload, signature)
