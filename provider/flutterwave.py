from typing import Optional, Any
from provider.base import BaseProvider
from model import PaymentResponse, ChargeRequest, PaymentStatus
from utils import to_minor_units, handle_http_errors, verify_paystack_signature
from core.config import logger

class FlutterwaveProvider(BaseProvider):
    providr_name = "flutterwave"
    base_url = "https://api.flutterwave.com/v3"

    async def initialize_payment(self, request: ChargeRequest) -> PaymentResponse:
        await super().initialize_payment(request)
        
        payload = {
            "tx_ref": request.reference,
            "amount": to_minor_units(request.amount, request.currency),
            "currency": request.currency,
            "redirect_url": request.callback_url,
            "payment_options": "card, mobilemoney, ussd",
            "customer": {
                "email": request.email,
                "name": request.metadata.get("name")
            },
            "meta": request.metadata
        }

        logger.debug(f"[{self.provider_name}] Initializing transaction: {request.reference}")
        
        response = await self._request_with_retry(
            "POST",
            f"{self.base_url}/payments",
            json={k: v for k, v in payload.items() if v is not None}
        )
        await handle_http_errors(response)
        
        data = response.json()["data"]
        return PaymentResponse(
            checkout_url=data["link"],
            reference=data["tx_ref"],
            status=PaymentStatus.PENDING,
            amount=request.amount,
            currency=request.currency,
            provider=self.provider_name,
            provider_raw_response=response.json()
        )