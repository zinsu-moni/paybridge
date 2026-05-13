import uuid
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from ..core.config import logger


class IdempotencyTracker:
    """
    Track in-flight requests to prevent duplicate charges if network errors occur.
    Uses idempotency keys to deduplicate requests within a time window.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Args:
            ttl_seconds: Time to live for tracking entries (default 1 hour)
        """
        self.ttl_seconds = ttl_seconds
        self._requests: Dict[str, Dict[str, Any]] = {}
    
    def generate_key(self) -> str:
        """Generate a unique idempotency key."""
        return str(uuid.uuid4())
    
    def start_request(self, key: str, provider_name: str, endpoint: str) -> bool:
        """
        Mark a request as in-flight.
        
        Returns:
            True if this is a new request, False if it's a duplicate.
        """
        self._cleanup_expired()
        
        if key in self._requests:
            entry = self._requests[key]
            logger.warning(
                f"[{provider_name}] Duplicate request detected: {endpoint} "
                f"(original started {(datetime.now() - entry['started_at']).total_seconds():.1f}s ago)"
            )
            return False
        
        self._requests[key] = {
            "provider": provider_name,
            "endpoint": endpoint,
            "started_at": datetime.now(),
            "response": None,
            "error": None,
        }
        
        logger.debug(f"[{provider_name}] Tracking request {key[:8]}... to {endpoint}")
        return True
    
    def record_response(self, key: str, response: Any):
        """Record successful response."""
        if key in self._requests:
            self._requests[key]["response"] = response
            self._requests[key]["completed_at"] = datetime.now()
            logger.debug(f"Idempotency tracker: response recorded for {key[:8]}...")
    
    def record_error(self, key: str, error: Exception):
        """Record error for a request."""
        if key in self._requests:
            self._requests[key]["error"] = error
            self._requests[key]["completed_at"] = datetime.now()
            logger.debug(f"Idempotency tracker: error recorded for {key[:8]}...")
    
    def get_cached_response(self, key: str) -> Optional[Any]:
        """Get cached response if available."""
        self._cleanup_expired()
        
        if key in self._requests:
            entry = self._requests[key]
            if entry["response"] is not None:
                logger.info(f"Returning cached response for idempotency key {key[:8]}...")
                return entry["response"]
        
        return None
    
    def _cleanup_expired(self):
        """Remove expired entries."""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._requests.items()
            if (now - entry["started_at"]).total_seconds() > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._requests[key]
            logger.debug(f"Idempotency tracker: cleaned up expired entry {key[:8]}...")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        self._cleanup_expired()
        return {
            "tracked_requests": len(self._requests),
            "entries": [
                {
                    "key": k[:8] + "...",
                    "provider": v["provider"],
                    "endpoint": v["endpoint"],
                    "age_seconds": (datetime.now() - v["started_at"]).total_seconds(),
                }
                for k, v in self._requests.items()
            ]
        }
