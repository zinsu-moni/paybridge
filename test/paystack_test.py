import asyncio
import hmac
import hashlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model.payments import ChargeRequest, PaymentStatus
from provider.paystack import PaystackProvider


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.is_success = True
        self.status_code = 200
        self.text = "OK"

    def json(self):
        return self._payload


async def _test_initialize_payment():
    provider = PaystackProvider(secret_key="sk_test_123")
    request = ChargeRequest(email="customer@example.com", amount=1000, currency="NGN")
    response_payload = {
        "data": {
            "authorization_url": "https://checkout.paystack.com/test",
            "reference": request.reference,
        }
    }

    with patch.object(
        provider,
        "_request_with_retry",
        new=AsyncMock(return_value=FakeResponse(response_payload)),
    ) as mock_request:
        response = await provider.initialize_payment(request)

    assert response.status == PaymentStatus.PENDING
    assert response.provider == "paystack"
    assert response.checkout_url == "https://checkout.paystack.com/test"
    assert response.reference == request.reference
    assert response.amount == 1000

    mock_request.assert_awaited_once()
    assert mock_request.await_args.args[0] == "POST"
    assert mock_request.await_args.args[1].endswith("/transaction/initialize")
    assert mock_request.await_args.kwargs["json"] == {
        "email": "customer@example.com",
        "amount": 100000,
        "currency": "NGN",
        "reference": request.reference,
    }


async def _test_verify_payment():
    provider = PaystackProvider(secret_key="sk_test_123")
    response_payload = {
        "data": {
            "id": 987654,
            "reference": "test_ref_123",
            "status": "success",
            "amount": 250000,
            "currency": "NGN",
            "gateway_response": "Approved",
        }
    }

    with patch.object(
        provider,
        "_request_with_retry",
        new=AsyncMock(return_value=FakeResponse(response_payload)),
    ) as mock_request:
        response = await provider.verify_payment("test_ref_123")

    assert response.status == PaymentStatus.SUCCESSFUL
    assert response.transaction_id == "987654"
    assert response.reference == "test_ref_123"
    assert response.amount == 2500.0
    assert response.currency == "NGN"
    assert response.message == "Approved"

    mock_request.assert_awaited_once()
    assert mock_request.await_args.args[0] == "GET"
    assert mock_request.await_args.args[1].endswith("/transaction/verify/test_ref_123")


async def _test_refund():
    provider = PaystackProvider(secret_key="sk_test_123")
    response_payload = {
        "data": {
            "transaction": {
                "id": 123,
                "reference": "test_ref_123",
            },
            "amount": 250000,
            "currency": "NGN",
        }
    }

    with patch.object(
        provider,
        "_request_with_retry",
        new=AsyncMock(return_value=FakeResponse(response_payload)),
    ) as mock_request:
        response = await provider.refund("123", amount=2500)

    assert response.status == PaymentStatus.REFUNDED
    assert response.transaction_id == "123"
    assert response.reference == "test_ref_123"
    assert response.amount == 2500.0
    assert response.currency == "NGN"

    mock_request.assert_awaited_once()
    assert mock_request.await_args.args[0] == "POST"
    assert mock_request.await_args.args[1].endswith("/refund")
    assert mock_request.await_args.kwargs["json"] == {
        "transaction": "123",
        "amount": 250000,
    }


async def _test_validate_webhook():
    secret_key = "sk_test_123"
    provider = PaystackProvider(secret_key=secret_key)
    payload = '{"event":"charge.success","data":{"reference":"test_ref_123"}}'
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()

    assert provider.validate_webhook(payload, signature) is True
    assert provider.validate_webhook(payload, "bad_signature") is False


def test_initialize_payment():
    asyncio.run(_test_initialize_payment())


def test_verify_payment():
    asyncio.run(_test_verify_payment())


def test_refund():
    asyncio.run(_test_refund())


def test_validate_webhook():
    asyncio.run(_test_validate_webhook())


if __name__ == "__main__":
    test_initialize_payment()
    test_verify_payment()
    test_refund()
    test_validate_webhook()
    print("Paystack gateway tests passed")
