# tests/test_paystack.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from provider.paystack import PaystackProvider
from model.payments import ChargeRequest, PaymentStatus

@pytest.mark.asyncio
async def test_initialize_payment():
    provider = PaystackProvider(secret_key="sk_test_5a45babc9b5568e9910b73cafb9aab28818fc943")
    
    # Mock the HTTP request
    with patch.object(provider, '_request_with_retry') as mock_request:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "authorization_url": "https://checkout.paystack.com/...",
                "reference": "test_ref_123"
            }
        }
        mock_request.return_value = mock_response
        
        request = ChargeRequest(
            email="test@example.com",
            amount=1000,
            currency="NGN"
        )
        response = await provider.initialize_payment(request)
        
        assert response.status == PaymentStatus.PENDING
        assert response.provider == "paystack"