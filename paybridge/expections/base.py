from typing import Any, Optional, Dict

class PayBridgeError(Exception):
    def __init__(
        self, 
        message: str, 
        code: Optional[str] = None, 
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        raw_response: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.raw_response = raw_response

    def __str__(self):
        base_msg = f"{self.__class__.__name__}: {self.message}"
        if self.code:
            base_msg += f" (Code: {self.code})"
        if self.status_code:
            base_msg += f" [HTTP {self.status_code}]"
        return base_msg


class UniPayError(PayBridgeError):
    pass


class AuthenticationError(UniPayError):
    pass


class ValidationError(UniPayError):
    pass


class ProviderError(UniPayError):
    pass


class RateLimitError(UniPayError):
    pass


class NetworkError(UniPayError):
    pass


class GatewayUnavailableError(UniPayError):
    """Raised when all payment gateways are unavailable."""
    pass


class ProviderUnavailable(UniPayError):
    """Raised when a payment provider is unavailable or all providers have been exhausted."""
    pass


class ConfigurationError(UniPayError):
    pass


class ResourceNotFoundError(UniPayError):
    pass
