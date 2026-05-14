import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar
import httpx
from ..model import ChargeRequest
from ..model import PaymentResponse, PaymentStatus
from ..core.config import settings, logger
from ..expections import NetworkError, RateLimitError
from ..utils.masking import mask_sensitive_data
from ..utils.circuit_breaker import CircuitBreaker
from ..utils.idempotency import IdempotencyTracker


T =  TypeVar("T")

class BaseProvider(ABC):
    provider_name: str
    base_url: str
    
    def __init__(
        self, 
        secret_key: str, 
        public_key: Optional[str] = None, 
        base_url: Optional[str] = None, 
        timeout: Optional[float] = None,
        idempotency_store: Optional[Any] = None,
        idempotency_storage_path: Optional[str] = None,
    ):
        self.secret_key = secret_key
        self.public_key = public_key
        self.base_url = base_url or self.base_url
        self.timeout = timeout or settings.default_timeout
        self._client = httpx.AsyncClient(
            headers=self._get_default_headers(),
            timeout=self.timeout
        )
        
        # Initialize circuit breaker
        if settings.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=settings.circuit_breaker_failure_threshold,
                recovery_timeout=settings.circuit_breaker_recovery_timeout,
                success_threshold=settings.circuit_breaker_success_threshold,
            )
        else:
            self._circuit_breaker = None
        
        # Initialize idempotency tracker
        self._idempotency_tracker = IdempotencyTracker(
            ttl_seconds=settings.idempotency_ttl_seconds,
            storage=idempotency_store,
            storage_path=idempotency_storage_path or settings.idempotency_storage_path,
        )

    def _get_default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "User-Agent": settings.user_agent
        }

    async def _request_with_retry(self, method: str, url: str, idempotency_key: Optional[str] = None, **kwargs: Any) -> httpx.Response:
        max_retries = settings.max_retries
        backoff_factor = settings.retry_backoff_factor
        masked_kwargs = mask_sensitive_data(kwargs, mask_pii=True)
        
        # Generate idempotency key if not provided
        if idempotency_key is None:
            idempotency_key = self._idempotency_tracker.generate_key()

        headers = dict(kwargs.get("headers") or {})
        headers.setdefault("Idempotency-Key", idempotency_key)
        kwargs["headers"] = headers
        
        # Check circuit breaker
        if self._circuit_breaker and not self._circuit_breaker.can_attempt_request(self.provider_name):
            logger.error(f"[{self.provider_name}] Circuit breaker is OPEN. Rejecting request to {url}")
            raise NetworkError(
                f"Provider {self.provider_name} is temporarily unavailable (circuit breaker open)"
            )
        
        # Check for cached response from previous request with same idempotency key
        cached_response = self._idempotency_tracker.get_cached_response(idempotency_key)
        if cached_response is not None:
            return cached_response
        
        # Start tracking this request
        is_new_request = self._idempotency_tracker.start_request(
            idempotency_key, self.provider_name, url
        )

        if not is_new_request:
            for _ in range(5):
                await asyncio.sleep(0.2)
                cached_response = self._idempotency_tracker.get_cached_response(idempotency_key)
                if cached_response is not None:
                    return cached_response
            raise NetworkError(f"Duplicate request already in progress for {self.provider_name}")

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"[{self.provider_name}] {method} {url} - Attempt {attempt + 1} - Payload: {masked_kwargs.get('json') or masked_kwargs.get('params') or 'None'}")
                response = await self._client.request(method, url, **kwargs)
                
                # Handle 429 rate limit with exponential backoff
                if response.status_code == 429:
                    if attempt < settings.rate_limit_max_retries:
                        sleep_time = settings.rate_limit_backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"[{self.provider_name}] Rate limited (429). Retrying in {sleep_time}s... "
                            f"(Attempt {attempt + 1}/{settings.rate_limit_max_retries})"
                        )
                        await asyncio.sleep(sleep_time)
                        continue
                    else:
                        logger.error(
                            f"[{self.provider_name}] Rate limited (429) - max retries ({settings.rate_limit_max_retries}) exceeded"
                        )
                        self._idempotency_tracker.record_error(idempotency_key, RateLimitError("Rate limit exceeded"))
                        if self._circuit_breaker:
                            self._circuit_breaker.record_failure(self.provider_name)
                        return response
                
                # Success - record it
                self._idempotency_tracker.record_response(idempotency_key, response)
                if self._circuit_breaker:
                    self._circuit_breaker.record_success(self.provider_name)
                return response
                
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                last_exception = e
                if attempt == max_retries:
                    logger.error(f"[{self.provider_name}] Max retries reached for {url}")
                    self._idempotency_tracker.record_error(idempotency_key, e)
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure(self.provider_name)
                    raise NetworkError(f"Network failure after {max_retries} retries: {str(e)}") from e
                
                sleep_time = backoff_factor * (2 ** attempt)
                logger.warning(f"[{self.provider_name}] Network error: {str(e)}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
        
        raise NetworkError("Request failed")
    

    async def initialize_payment(self, request: ChargeRequest) -> PaymentResponse:
        """Initialize a payment. Override in concrete providers if needed."""
        logger.info(f"[{self.provider_name}] Initializing payment for request: {request.reference} for {request.email}")
        return None
    
    async def verify_payment(self, reference: str) -> PaymentResponse:
        """Verify a payment by reference. Override in concrete providers if needed."""
        logger.info(f"[{self.provider_name}] Verifying payment for reference: {reference}")
        return None
    
    async def refund(self, transaction_id: str, amount: Optional[float] = None, currency: Optional[str] = None) -> PaymentResponse:
        if amount:
            logger.info(f"[{self.provider_name}] Refunding payment for transaction: {transaction_id} | Amount: {amount:.2f} {currency}")
        else:
            logger.info(f"[{self.provider_name}] Refunding payment for transaction: {transaction_id}")
        return None
    
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
