def to_minor_units(amount: float, currency: str) -> int:
    return int(amount * 100)

def from_minor_units(amount: int, currency: str) -> float:
    return amount / 100.0
