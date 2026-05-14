# PayBridge

[![PyPI version](https://badge.fury.io/py/paybridge.svg)](https://pypi.org/project/paybridge/)  
Unified, modular payment gateway integration for Python. Connect to Paystack, Flutterwave, Monnify, and more with a single, developer-friendly API.

---

## Features
- Unified API for multiple payment gateways
- Modular, extensible provider system
- Circuit breaker and idempotency support
- Fallback and load-balancing between providers
- Webhook and refund handling
- FastAPI and Flask integration
- Type-safe models (Pydantic)

---

## Installation
```bash
pip install paybridge
```

---

## Quick Start
```python
from paybridge import PayBridge

paybridge = PayBridge(
    provider="paystack",
    secret_key="sk_test_xxxxxxxxx"
)

response = paybridge.initialize_payment(
    amount=5000,
    email="customer@example.com",
    currency="NGN",
    reference="TXN_001"
)
print(response)
```

---

## Multi-Gateway Example
```python
from paybridge import PayBridge

paystack = PayBridge(provider="paystack", secret_key="PAYSTACK_SECRET")
flutterwave = PayBridge(provider="flutterwave", secret_key="FLUTTERWAVE_SECRET")

try:
    response = paystack.initialize_payment(amount=5000, email="customer@example.com")
except Exception:
    response = flutterwave.initialize_payment(amount=5000, email="customer@example.com")
print(response)
```

---

## Supported Providers
- Paystack
- Flutterwave
- Monnify (in progress)
- Stripe (planned)

---

## Environment Variables
Never hardcode secret keys in production. Use a `.env` file:
```
PAYSTACK_SECRET_KEY=sk_test_xxxxx
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST_xxxxx
```
And load with python-dotenv:
```python
from dotenv import load_dotenv
import os
load_dotenv()
secret_key = os.getenv("PAYSTACK_SECRET_KEY")
```

---

## FastAPI Example
```python
from fastapi import FastAPI
from paybridge import PayBridge

app = FastAPI()
paybridge = PayBridge(provider="paystack", secret_key="sk_test_xxxxxxxxx")

@app.post("/initialize-payment")
async def initialize_payment():
    response = paybridge.initialize_payment(
        amount=5000,
        email="customer@example.com",
        currency="NGN",
        reference="TXN_001"
    )
    return response
```

---

## Error Handling Example
```python
try:
    response = paybridge.initialize_payment(amount=5000, email="customer@example.com")
    print(response)
except Exception as e:
    print(f"Payment failed: {e}")
```

---

## License
MIT License
