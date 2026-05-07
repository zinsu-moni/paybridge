from typing import Any, Dict, Optional
import httpx
from expections.base import (
    PayBridgeError,
    AuthenticationError,
    RateLimitError,
    ProviderError,
    NetworkError,
    ResourceNotFoundError,
    ValidationError,
)
from core.config import logger

async def handle_http_errors(response: httpx.Response):
    if response.is_success:
        return
    
    status_code = response.status_code
    try:
        error_data = response.json()
    except Exception:
        error_data = {"message": response.text}

    message = error_data.get("message") or error_data.get("error") or "An unknown error occurred with the payment provider."
    code = error_data.get("code")
    
    logger.error(f"Provider error: {status_code} - {message} (Code: {code})")

    if status_code == 401:
        raise AuthenticationError(message, code=code, status_code=status_code, details=error_data, raw_response=error_data)
    elif status_code == 404:
        raise ResourceNotFoundError(message, code=code, status_code=status_code, details=error_data, raw_response=error_data)
    elif status_code == 422:
        raise ValidationError(message, code=code, status_code=status_code, details=error_data, raw_response=error_data)
    elif status_code == 429:
        raise RateLimitError(message, code=code, status_code=status_code, details=error_data, raw_response=error_data)
    elif 400 <= status_code < 500:
        raise ProviderError(message, code=code, status_code=status_code, details=error_data, raw_response=error_data)
    else:
        raise NetworkError(f"Server error: {status_code}", status_code=status_code, details=error_data, raw_response=error_data)
