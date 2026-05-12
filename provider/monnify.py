from typing import Optional, Any
from provider.base import BaseProvider
from model import PaymentResponse, ChargeRequest, PaymentStatus
from utils import to_minor_units, handle_http_errors, verify_paystack_signature
from core.config import logger


class MonnifyProvider(BaseProvider):
    provider_name = "monnify"
    base_url = "https://api.monnify.com/api/v1"

    async def initialize_payment(self, request: ChargeRequest) -> PaymentResponse:
        await super().initialize_payment(request)
        
        payload = {
            "amount": to_minor_units(request.amount, request.currency),
            "currencyCode": request.currency,
            "paymentReference": request.reference,
            "redirectUrl": request.callback_url,
            "customerName": request.metadata.get("name"),
            "customerEmail": request.email,
            "customerMobileNumber": request.metadata.get("mobile"),
            "metaData": request.metadata
        }

        logger.debug(f"[{self.provider_name}] Initializing transaction: {request.reference}")
        
        response = await self._request_with_retry(
            "POST",
            f"{self.base_url}/merchant/transactions/init-transaction",
            json={k: v for k, v in payload.items() if v is not None}
        )
        await handle_http_errors(response)
        
        data = response.json()["responseBody"]
        return PaymentResponse(
            checkout_url=data["checkoutUrl"],
            reference=data["paymentReference"],
            status=PaymentStatus.PENDING,
            amount=request.amount,
            currency=request.currency,
            provider=self.provider_name,
            provider_raw_response=response.json()
        )