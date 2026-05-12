from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

class PayBrigde(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True
    )

class Money(BaseModel):
    amount: float
    currency: str

class Customer(PayBrigde):
    id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

UniPayBaseModel = PayBrigde

    