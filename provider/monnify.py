from typing import Optional, Any
from provider.base import BaseProvider
from model import PaymentResponse, ChargeRequest, PaymentStatus
from utils import to_minor_units, handle_http_errors, verify_paystack_signature
from core.config import logger
import base64


class MonnifyProvider(BaseProvider):
    provider_name = "monnify"
    base_url = "https://api.monnify.com/api/v1"

    def __init__(
        self, 
        secret_key: str, 
        public_key: Optional[str] = None, 
        monnify_secret: Optional[str] = None, 
        base_url: Optional[str] = None, 
        **kwargs: Any
    ):
        super().__init__(secret_key, public_key, base_url, **kwargs)
        self.monnify_secret = monnify_secret
        self._access_token: Optional[str] = None

    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        auth_str = f"{self.secret_key}:{self.monnify_secret}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        
        response = await self._client.post(
            f"{self.base_url}/auth/login",
            headers={"Authorization": f"Basic {encoded_auth}"}
        )
        await handle_http_errors(response)
        
        self._access_token = response.json()["responseBody"]["accessToken"]
        return self._access_token

    def _get_default_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json"
        }

    async def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> Any:
    
        token = await self._get_access_token()
        kwargs.setdefault("headers", {})["Authorization"] = f"Bearer {token}"
        return await super()._request_with_retry(method, url, **kwargs)

    async def initialize_payment(self, request: ChargeRequest) -> PaymentResponse:
        
        await super().initialize_payment(request)
        
        payload = {
            "amount": request.amount,
            "customerName": f"{request.email}",
            "customerEmail": request.email,
            "paymentReference": request.reference,
            "paymentDescription": "UniPay Payment",
            "currencyCode": request.currency,
            "contractCode": request.metadata.get("contract_code") if request.metadata else None,
            "redirectUrl": request.callback_url,
            "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
        }

        response = await self._request_with_retry(
            "POST",
            f"{self.base_url}/merchant/transactions/init-transaction",
            json={k: v for k, v in payload.items() if v is not None},
            idempotency_key=request.reference
        )
        await handle_http_errors(response)
        
        body = response.json()["responseBody"]
        return PaymentResponse(
            checkout_url=body["checkoutUrl"],
            reference=body["paymentReference"],
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
            f"{self.base_url}/merchant/transactions/query?paymentReference={reference}"
        )

        await handle_http_errors(response)

        body =response.json()["responseBody"]
        status_map = {
            "succesful": PaymentStatus.SUCCESSFUL,
            "failed": PaymentStatus.FAILED,
            "cancelled": PaymentStatus.CANCELLED,
            "pending": PaymentStatus.PENDING,
        }

        return PaymentResponse(
            transaction_id=str(body["transactionId"]),
            reference=body["paymentReference"],
            status=status_map.get(body["transactionStatus"].lower(), PaymentStatus.PROCESSING),
            amount=body["amountPaid"],
            currency=body["currency"],
            provider=self.provider_name,
            message=body.get("paymentDescription"),
            provider_raw_response=response.json()
        )