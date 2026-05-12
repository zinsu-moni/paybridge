# PayBridge Documentation

Unified payment gateway integration for Python developers.

PayBridge provides a single interface for integrating multiple payment gateways without rewriting payment logic for every provider.

---

# Features

- Unified payment API
- Multiple gateway support
- Easy provider switching
- Fallback gateway handling
- Payment verification
- Refund support
- Webhook handling
- Scalable architecture
- Developer-friendly API
- FastAPI support

---

# Supported Providers

- Paystack
- Flutterwave
- Monnify
- Stripe
- More coming soon

---

# Installation

Install PayBridge using pip:

```bash
pip install paybridge
```

Upgrade to the latest version:

```bash
pip install --upgrade paybridge
```

---

# Quick Start

## Import PayBridge

```python
from paybridge import PayBridge
```

---

# Initialize a Provider

## Paystack Example

```python
paybridge = PayBridge(
    provider="paystack",
    secret_key="sk_test_xxxxxxxxx"
)
```

---

# Initialize Payment

```python
response = paybridge.initialize_payment(
    amount=5000,
    email="customer@example.com",
    currency="NGN",
    reference="TXN_001"
)

print(response)
```

---

# Verify Payment

Always verify payments server-side after payment completion.

```python
verification = paybridge.verify_payment(
    reference="TXN_001"
)

print(verification)
```

---

# Charge a Customer

```python
response = paybridge.charge(
    amount=10000,
    email="customer@example.com"
)

print(response)
```

---

# Refund a Payment

```python
refund = paybridge.refund(
    reference="TXN_001",
    amount=5000
)

print(refund)
```

---

# Webhook Handling

Webhooks allow your application to receive real-time payment events.

## Flask Example

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json

    print(payload)

    return {"status": "success"}
```

---

# Using Multiple Gateways

One of PayBridge’s most powerful features is multi-gateway support.

This allows developers to:
- Create fallback systems
- Reduce downtime
- Route payments dynamically
- Improve reliability
- Avoid vendor lock-in

---

# Initialize Multiple Providers

```python
from paybridge import PayBridge

paystack = PayBridge(
    provider="paystack",
    secret_key="PAYSTACK_SECRET_KEY"
)

flutterwave = PayBridge(
    provider="flutterwave",
    secret_key="FLUTTERWAVE_SECRET_KEY"
)
```

---

# Gateway Fallback Example

If one provider fails, automatically switch to another.

```python
try:
    response = paystack.initialize_payment(
        amount=5000,
        email="customer@example.com"
    )

except Exception:
    response = flutterwave.initialize_payment(
        amount=5000,
        email="customer@example.com"
    )

print(response)
```

---

# Dynamic Provider Selection

```python
def get_provider(currency):
    if currency == "NGN":
        return paystack

    return flutterwave


provider = get_provider("NGN")

response = provider.initialize_payment(
    amount=10000,
    email="customer@example.com"
)

print(response)
```

---

# Provider Configuration System

```python
providers = {
    "paystack": PayBridge(
        provider="paystack",
        secret_key="PAYSTACK_SECRET"
    ),

    "flutterwave": PayBridge(
        provider="flutterwave",
        secret_key="FLUTTERWAVE_SECRET"
    )
}
```

Using a provider dynamically:

```python
selected_provider = providers["paystack"]

response = selected_provider.initialize_payment(
    amount=5000,
    email="customer@example.com"
)
```

---

# Smart Routing Example

```python
def route_payment(amount):
    if amount > 100000:
        return flutterwave

    return paystack


provider = route_payment(5000)

response = provider.initialize_payment(
    amount=5000,
    email="customer@example.com"
)
```

---

# Retry Logic Example

```python
providers = [paystack, flutterwave]

for provider in providers:
    try:
        response = provider.initialize_payment(
            amount=5000,
            email="customer@example.com"
        )

        print("Payment initialized successfully")
        break

    except Exception as e:
        print(f"Provider failed: {e}")
```

---

# FastAPI Integration

This section shows how to integrate PayBridge into a FastAPI application.

---

# Install FastAPI Dependencies

```bash
pip install fastapi uvicorn
```

---

# Basic FastAPI Integration

```python
from fastapi import FastAPI
from paybridge import PayBridge

app = FastAPI()

paybridge = PayBridge(
    provider="paystack",
    secret_key="sk_test_xxxxxxxxx"
)


@app.get("/")
async def home():
    return {"message": "PayBridge API Running"}


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

# Run FastAPI Server

```bash
uvicorn main:app --reload
```

---

# FastAPI Verify Payment Example

```python
@app.get("/verify-payment/{reference}")
async def verify_payment(reference: str):

    verification = paybridge.verify_payment(
        reference=reference
    )

    return verification
```

---

# FastAPI Request Body Example

```python
from pydantic import BaseModel


class PaymentRequest(BaseModel):
    amount: int
    email: str
    currency: str = "NGN"


@app.post("/pay")
async def pay(data: PaymentRequest):

    response = paybridge.initialize_payment(
        amount=data.amount,
        email=data.email,
        currency=data.currency
    )

    return response
```

---

# FastAPI Multi-Gateway Example

```python
from fastapi import FastAPI
from paybridge import PayBridge

app = FastAPI()

paystack = PayBridge(
    provider="paystack",
    secret_key="PAYSTACK_SECRET"
)

flutterwave = PayBridge(
    provider="flutterwave",
    secret_key="FLUTTERWAVE_SECRET"
)


@app.post("/payment")
async def payment():

    try:
        response = paystack.initialize_payment(
            amount=5000,
            email="customer@example.com"
        )

    except Exception:

        response = flutterwave.initialize_payment(
            amount=5000,
            email="customer@example.com"
        )

    return response
```

---

# FastAPI Dynamic Routing Example

```python
def get_provider(currency: str):

    if currency == "NGN":
        return paystack

    return flutterwave


@app.post("/dynamic-payment")
async def dynamic_payment(data: PaymentRequest):

    provider = get_provider(data.currency)

    response = provider.initialize_payment(
        amount=data.amount,
        email=data.email,
        currency=data.currency
    )

    return response
```

---

# FastAPI Webhook Example

```python
from fastapi import Request


@app.post("/webhook")
async def webhook(request: Request):

    payload = await request.json()

    print(payload)

    return {
        "status": "success"
    }
```

---

# FastAPI Refund Example

```python
@app.post("/refund/{reference}")
async def refund(reference: str):

    response = paybridge.refund(
        reference=reference,
        amount=5000
    )

    return response
```

---

# Environment Variables

Never hardcode secret keys in production.

## Example `.env`

```env
PAYSTACK_SECRET_KEY=sk_test_xxxxx
FLUTTERWAVE_SECRET_KEY=FLWSECK_TEST_xxxxx
```

---

# Using python-dotenv

```python
from dotenv import load_dotenv
import os

load_dotenv()

secret_key = os.getenv("PAYSTACK_SECRET_KEY")
```

---

# Full Integration Example

```python
from paybridge import PayBridge

paybridge = PayBridge(
    provider="paystack",
    secret_key="sk_test_xxxxx"
)

payment = paybridge.initialize_payment(
    amount=5000,
    email="customer@example.com",
    currency="NGN",
    reference="TXN_001"
)

print(payment)
```

---

# Recommended Architecture

```text
Client Request
      ↓
FastAPI Routes
      ↓
Payment Service
      ↓
Provider Router
      ↓
Paystack / Flutterwave / Stripe
```

This architecture provides:
- Scalability
- Reliability
- Easier maintenance
- Better failover handling

---

# Error Handling

Always handle payment failures properly.

```python
try:
    response = paybridge.initialize_payment(
        amount=5000,
        email="customer@example.com"
    )

    print(response)

except Exception as e:
    print(f"Payment failed: {e}")
```

---

# FastAPI Error Handling

```python
from fastapi import HTTPException


@app.post("/safe-payment")
async def safe_payment():

    try:

        response = paybridge.initialize_payment(
            amount=5000,
            email="customer@example.com"
        )

        return response

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
```

---

# Best Practices

- Always verify payments server-side
- Use environment variables for secret keys
- Implement webhook verification
- Add retry mechanisms
- Log failed transactions
- Monitor provider downtime
- Use fallback gateways
- Track transaction success rates
- Separate payment logic into services

---

# Why PayBridge?

PayBridge helps developers:
- Reduce integration complexity
- Switch providers easily
- Build scalable fintech systems faster
- Avoid vendor lock-in
- Maintain cleaner codebases

---

# Contributing

Contributions are welcome.

## Steps

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your fork
5. Open a pull request

---

# License

MIT License

---

# Support

GitHub Repository:

https://github.com/zinsu-moni/paybridge

Issues:

https://github.com/zinsu-moni/paybridge/issues