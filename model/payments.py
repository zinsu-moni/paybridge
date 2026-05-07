import uuid
from enum import Enum
from typing import Optional, Any
from pydantic import Field, field_validator
from .base import PayBrigde, Money, Customer

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentResponse(PayBrigde):
    transaction_id: Optional[str] = None
    reference: Optional[str] = None
    checkout_url: Optional[str] = None
    status: PaymentStatus
    amount: float
    currency: str
    provider: str
    message: Optional[str] = None
    provider_raw_response: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None

class ChargeRequest(PayBrigde):
    amount: float = Field(..., gt=0, description="Amount must be greater than 0")
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    email: str
    phone: Optional[str] = None
    reference: str = Field(default_factory=lambda: f"uni_{uuid.uuid4().hex[:12]}")
    callback_url: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v


ChargesRequest = ChargeRequest


