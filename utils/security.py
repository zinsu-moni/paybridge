import hmac
import hashlib
from typing import Optional

def verify_paystack_signature(secret_key: str, payload: str, signature: str) -> bool:
    hash_object = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha512
    )
    expected_signature = hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature)
