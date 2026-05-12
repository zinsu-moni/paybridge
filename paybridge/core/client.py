from typing import Type, TypeVar, Optional, Any, Dict
from ..provider.base import BaseProvider
from ..provider.paystack import PaystackProvider
# from ..provider.flutterwave import FlutterwaveProvider
# from ..provider.monnify import MonnifyProvider
from ..expections.base import ConfigurationError, ValidationError
from ..model.payments import PaymentResponse, ChargeRequest
from .config import settings, logger
from pydantic import ValidationError as PydanticValidationError

T = TypeVar("T", bound=BaseProvider)

class PayBridge:
    _PROVIDER_REGISTRY: Dict[str, Type[BaseProvider]] = {
        "paystack": PaystackProvider,
        # "flutterwave": FlutterwaveProvider,
        # "monnify": MonnifyProvider,
    }

    def __init__(
        self, 
        provider: Optional[str] = None, 
        secret_key: Optional[str] = None, 
        public_key: Optional[str] = None,
        debug: bool = False,
        timeout: Optional[float] = None,
        **kwargs: Any
    ):
        
        if debug:
            settings.debug = True
        
        settings.setup_logging()
        
        self._providers: dict[str, BaseProvider] = {}
        self._default_provider: Optional[BaseProvider] = None

        if provider:
            if not secret_key:
                raise ConfigurationError("secret_key is required when initializing with a provider.")
            self._default_provider = self.use_provider_by_name(
                provider, 
                secret_key, 
                public_key=public_key,
                timeout=timeout,
                **kwargs
            )

    def use_provider_by_name(
        self, 
        name: str, 
        secret_key: str, 
        public_key: Optional[str] = None,
        set_as_default: bool = False, 
        **kwargs: Any
    ) -> BaseProvider:
        if name not in self._PROVIDER_REGISTRY:
            raise ConfigurationError(
                f"Provider '{name}' is not supported. Supported: {list(self._PROVIDER_REGISTRY.keys())}"
            )
        
        provider_class = self._PROVIDER_REGISTRY[name]
        return self.use_provider(
            provider_class, 
            secret_key, 
            public_key=public_key,
            set_as_default=set_as_default, 
            **kwargs
        )

    def use_provider(
        self, 
        provider_class: Type[T], 
        secret_key: str, 
        public_key: Optional[str] = None,
        set_as_default: bool = False, 
        **kwargs: Any
    ) -> T:
        provider = provider_class(
            secret_key=secret_key, 
            public_key=public_key,
            **kwargs
        )
        self._providers[provider.provider_name] = provider
        
        if set_as_default or not self._default_provider:
            self._default_provider = provider
            logger.info(f"Set default provider to: {provider.provider_name}")
        
        logger.info(f"Initialized provider: {provider.provider_name}")
        return provider

    def get_provider(self, name: Optional[str] = None) -> BaseProvider:
        if name is None:
            if not self._default_provider:
                raise ConfigurationError("No default provider initialized. Please provide a 'provider' name.")
            return self._default_provider
            
        if name not in self._providers:
            raise ConfigurationError(f"Provider '{name}' is not registered.")
        return self._providers[name]

    async def initialize_payment(
        self, 
        email: str, 
        amount: float, 
        currency: str = "NGN", 
        reference: Optional[str] = None,
        provider: Optional[str] = None,
        **kwargs: Any
    ) -> PaymentResponse:
        provider_instance = self.get_provider(provider)
        
        try:
            request_data = {
                "email": email,
                "amount": amount,
                "currency": currency,
                **kwargs
            }
            if reference:
                request_data["reference"] = reference
                
            request = ChargeRequest(**request_data)
        except PydanticValidationError as e:
            logger.error(f"Validation error: {e}")
            raise ValidationError(f"Invalid request data: {str(e)}", details=e.errors())

        logger.info(f"[{provider_instance.provider_name}] Initializing payment for {email} ({amount} {currency})")
        return await provider_instance.initialize_payment(request)

    async def verify_payment(self, reference: str, provider: Optional[str] = None) -> PaymentResponse:
        provider_instance = self.get_provider(provider)
        logger.info(f"[{provider_instance.provider_name}] Verifying payment: {reference}")
        return await provider_instance.verify_payment(reference)

    async def close_all(self):
        for provider in self._providers.values():
            await provider.close()

    def __repr__(self) -> str:
        providers = list(self._providers.keys())
        default = self._default_provider.provider_name if self._default_provider else "None"
        return f"UniPay(providers={providers}, default={default})"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_all()
