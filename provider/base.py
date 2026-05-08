import asyncio
import time 
from abc import ABC, abstractclassmethod
from typing import Any, Dict, List, Optional, TypeVar
import httpx
from model import PaymentResponse, PaymentStatus
from core.config import settings, logger
from expections import NetworkError

T =  TypeVar("T")

class BaseProvider(ABC):
    provider_name: str
    base_url: str
    
    def __init__(
        self, 
        secret_key: str, 
        public_key: Optional[str] = None, 
        base_url: Optional[str] = None, 
        timeout: Optional[float] = None
    ):
        self.secret_key = secret_key
        self.public_key = public_key
        self.base_url = base_url or self.base_url
        self.timeout = timeout or settings.default_timeout
        self._client = httpx.AsyncClient(
            headers=self._get_default_headers(),
            timeout=self.timeout
        )



