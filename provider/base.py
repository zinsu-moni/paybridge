import asyncio
import time 
from abc import ABC, abstractclassmethod
from typing import Any, Dict, List, Optional, TypeVar
import httpx
from unipay import ChargeRequest
from model import PaymentResponse, PaymentStatus
from core.config import settings, logger
from expections import NetworkError
from utils.masking import mask_sensitive_data


T =  TypeVar("T")

class BaseProvider(ABC):
    provider_name: str
    base_url: str
    
    def __init__(
        self, 
        secret_key: str, 
        public_key: Optional[str] = None, 
        base_url: Optional[str] = None, 
        timeout: Optional[float] = None
    ):
        self.secret_key = secret_key
        self.public_key = public_key
        self.base_url = base_url or self.base_url
        self.timeout = timeout or settings.default_timeout
        self._client = httpx.AsyncClient(
            headers=self._get_default_headers(),
            timeout=self.timeout
        )

    def _get_dafault_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "User-Agent": settings.user_agent
        }

    async def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        max_retries = settings.max_retries
        backoff_factor = settings.retry_backoff_factor
        masked_kwargs = mask_sensitive_data(kwargs, mask_pii=True)


        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"[{self.provider_name}] {method} {url} - Attempt {attempt + 1} - Payload: {masked_kwargs.get('json') or masked_kwargs.get('params') or 'None'}")
                response = await self._client.request(method, url, **kwargs)
                return response
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                last_exception = e
                if attempt == max_retries:
                    logger.error(f"[{self.provider_name}] Max retries reached for {url}")
                    raise NetworkError(f"Network failure after {max_retries} retries: {str(e)}") from e
                
                sleep_time = backoff_factor * (2 ** attempt)
                logger.warning(f"[{self.provider_name}] Network error: {str(e)}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
        
        raise NetworkError("Request failed")
    

    @abstractclassmethod
    async def initalize_payment(self, request: ChargeRequest) -> PaymentResponse:
        logger.info(f"[{self.provider_name}] Initializing payment for request: {request.reference} for {request.email}")
        return None
    
    @abstractclassmethod
    async def verify_payment(self, reference: str) -> PaymentStatus:
        logger.info(f"[{self.provider_name}] Verifying payment for reference: {reference}")
        return None
    
    @abstractclassmethod
    async def refund(self, transaction_id: str, amount: Optional[float] = None) -> PaymentResponse:
        log_amount = f"{amount:.2f}" if amount else ""
        logger.info(f"[{self.provider_name}] Refunding payment for transaction: {transaction_id}{log_amount}")
        return None
    
    @abstractclassmethod
    def validate_webhook(self, payload: Dict[str, Any], signature: str) -> bool:
        logger.info(f"[{self.provider_name}] Validating webhook with payload: {mask_sensitive_data(payload)}")
        return False
    

    async def charge(self, request: ChargeRequest) -> PaymentResponse:
        return await self.initialize_payment(request)

    async def verify_transaction(self, transaction_id: str) -> PaymentResponse:
        return await self.verify_payment(transaction_id)

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
