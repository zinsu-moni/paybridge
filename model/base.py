from pydantic import BaaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any

class PayBrigde(BaaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True
    )

class Money(BaaseModel):
    amount: float
    currency: str

class Customer(PayBrigde):
    id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    