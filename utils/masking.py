import re
from typing import Any, Union, Dict, List

SENSITIVE_FIELDS = {
    "api_key", "secret_key", "public_key", "token", "access_token", 
    "password", "cvv", "card_number", "pin", "authorization",
}

PII_FIELDS = {
    "email", "phone", "first_name", "last_name", "customer_name"
}

def mask_sensitive_data(data: Union[Dict, List, str, Any], mask_pii: bool = False) -> Any:

    if isinstance(data, dict):
        masked_dict = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in SENSITIVE_FIELDS or (mask_pii and key_lower in PII_FIELDS):
                masked_dict[key] = "********"
            elif key_lower == "authorization" and isinstance(value, str):
                # Mask Bearer tokens but keep the prefix
                if value.lower().startswith("bearer "):
                    masked_dict[key] = "Bearer ********"
                else:
                    masked_dict[key] = "********"
            else:
                masked_dict[key] = mask_sensitive_data(value, mask_pii)
        return masked_dict
    elif isinstance(data, list):
        return [mask_sensitive_data(item, mask_pii) for item in data]
    elif isinstance(data, str):
        return data
    return data

def mask_string(value: str, visible_chars: int = 4) -> str:
    if not value or len(value) <= visible_chars:
        return "********"
    return f"{value[:visible_chars]}********{value[-visible_chars:]}"
