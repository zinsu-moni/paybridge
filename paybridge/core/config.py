import logging
from ..model.base import PayBrigde
from pydantic import ConfigDict

logger = logging.getLogger("PayBridge")

class SDKConfig(PayBrigde):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_agent: str = "PayBridge SDK/1.0"
    default_timeout: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    
    # Rate limit (429) backoff settings
    rate_limit_max_retries: int = 5
    rate_limit_backoff_factor: float = 1.0  # Start with 1s, exponential growth
    
    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60  # seconds
    circuit_breaker_success_threshold: int = 2
    
    # Idempotency tracking
    idempotency_ttl_seconds: int = 3600  # 1 hour
    
    debug: bool = False
    
    log_level: int = logging.INFO

    def setup_logging(self):
        level = logging.DEBUG if self.debug else self.log_level
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)


settings = SDKConfig()