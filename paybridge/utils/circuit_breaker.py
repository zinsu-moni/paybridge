import time
from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timedelta
from ..core.config import logger


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Fail fast, provider is down
    HALF_OPEN = "half_open"  # Testing if provider has recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for payment providers.
    Prevents cascading failures by failing fast when a provider is consistently down.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        """
        Args:
            failure_threshold: Number of consecutive failures to open circuit
            recovery_timeout: Seconds to wait before attempting recovery (half-open)
            success_threshold: Number of successes in half-open state to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    def record_success(self, provider_name: str):
        """Record a successful request."""
        if self.state == CircuitState.CLOSED:
            self.failure_count = 0
            return
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(
                f"[{provider_name}] Circuit breaker: success {self.success_count}/{self.success_threshold} in half-open state"
            )
            
            if self.success_count >= self.success_threshold:
                self.close(provider_name)
    
    def record_failure(self, provider_name: str):
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        logger.warning(
            f"[{provider_name}] Circuit breaker: failure {self.failure_count}/{self.failure_threshold}"
        )
        
        if self.failure_count >= self.failure_threshold:
            self.open(provider_name)
    
    def can_attempt_request(self, provider_name: str) -> bool:
        """Check if a request can be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.half_open(provider_name)
                return True
            return False
        
        # HALF_OPEN state - allow requests
        return True
    
    def _should_attempt_recovery(self) -> bool:
        """Check if recovery timeout has elapsed."""
        if not self.last_failure_time:
            return False
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def open(self, provider_name: str):
        """Open the circuit (provider is down)."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            logger.error(
                f"[{provider_name}] Circuit breaker OPENED: provider marked as down"
            )
    
    def half_open(self, provider_name: str):
        """Half-open the circuit (testing recovery)."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.warning(
            f"[{provider_name}] Circuit breaker HALF-OPEN: attempting recovery after {self.recovery_timeout}s"
        )
    
    def close(self, provider_name: str):
        """Close the circuit (provider is healthy)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"[{provider_name}] Circuit breaker CLOSED: provider recovered")
    
    def get_state(self) -> str:
        """Get current circuit state."""
        return self.state.value
