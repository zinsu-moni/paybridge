"""
Enhanced PayBridge client with multi-gateway support.
Integrates the MultiGatewayRouter for intelligent provider routing and failover.

Usage:
    # Initialize with multiple providers
    bridge = PayBridgeMultiGateway()
    
    # Add providers with priority
    bridge.add_gateway(
        name="paystack",
        provider=PaystackProvider(secret_key="..."),
        priority=0,  # Primary
        max_load_percent=70
    )
    bridge.add_gateway(
        name="flutterwave",
        provider=FlutterwaveProvider(secret_key="..."),
        priority=1,  # Fallback
        max_load_percent=30
    )
    
    # Use primary/fallback routing (automatic failover)
    response = await bridge.charge(
        amount=10000,
        email="customer@example.com",
        strategy="primary_fallback"
    )
    
    # Or use load balancing across healthy providers
    response = await bridge.charge(
        amount=5000,
        email="customer@example.com",
        strategy="load_balance"
    )
    
    # Monitor provider health
    health = bridge.get_health_status()
    print(health)
"""

from typing import Optional, Any, Dict
from .gateway_router import MultiGatewayRouter, ProviderHealth
from ..provider.base import BaseProvider
from ..provider.paystack import PaystackProvider
from ..provider.flutterwave import FlutterwaveProvider
from ..expections.base import ConfigurationError, ValidationError, GatewayUnavailableError
from ..model.payments import PaymentResponse, ChargeRequest
from .config import settings, logger
from pydantic import ValidationError as PydanticValidationError


class PayBridgeMultiGateway:
    """
    Multi-gateway payment router with intelligent failover and load balancing.
    
    Features:
    - Primary/fallback routing with automatic retry
    - Load balancing across healthy providers
    - Real-time health monitoring
    - Provider enable/disable
    - Comprehensive error handling
    """
    
    _PROVIDER_REGISTRY = {
        "paystack": PaystackProvider,
        "flutterwave": FlutterwaveProvider,
    }
    
    def __init__(
        self,
        debug: bool = False,
        default_strategy: str = "primary_fallback",
        timeout: Optional[float] = None,
    ):
        """
        Initialize PayBridge with multi-gateway support.
        
        Args:
            debug: Enable debug logging
            default_strategy: "primary_fallback" or "load_balance"
            timeout: Default timeout for all providers
        """
        if debug:
            settings.debug = True
        
        settings.setup_logging()
        
        self.router = MultiGatewayRouter(default_strategy=default_strategy)
        self.timeout = timeout or settings.default_timeout
        self._default_gateway: Optional[str] = None
        
        logger.info(f"PayBridgeMultiGateway initialized (strategy={default_strategy})")
    
    # =========================================================================
    # Gateway Management
    # =========================================================================
    
    def add_gateway_by_name(
        self,
        name: str,
        secret_key: str,
        public_key: Optional[str] = None,
        priority: int = 0,
        enabled: bool = True,
        max_load_percent: float = 100.0,
        **kwargs
    ) -> BaseProvider:
        """
        Add a payment provider by name (paystack, flutterwave, etc).
        
        Args:
            name: Provider name (must be in _PROVIDER_REGISTRY)
            secret_key: Provider secret key
            public_key: Provider public key (if applicable)
            priority: Lower number = higher priority (0 is primary)
            enabled: Whether provider is initially enabled
            max_load_percent: Max % of requests this provider handles
            **kwargs: Additional provider-specific kwargs
        
        Returns:
            The provider instance
        """
        if name not in self._PROVIDER_REGISTRY:
            raise ConfigurationError(
                f"Provider '{name}' not supported. "
                f"Supported: {list(self._PROVIDER_REGISTRY.keys())}"
            )
        
        provider_class = self._PROVIDER_REGISTRY[name]
        provider = provider_class(
            secret_key=secret_key,
            public_key=public_key,
            timeout=self.timeout,
            **kwargs
        )
        
        self.router.add_provider(
            name=name,
            provider=provider,
            priority=priority,
            enabled=enabled,
            max_load_percent=max_load_percent,
        )
        
        if not self._default_gateway or priority == 0:
            self._default_gateway = name
        
        logger.info(
            f"Gateway '{name}' added (priority={priority}, "
            f"enabled={enabled}, load_limit={max_load_percent}%)"
        )
        
        return provider
    
    def add_gateway(
        self,
        name: str,
        provider: BaseProvider,
        priority: int = 0,
        enabled: bool = True,
        max_load_percent: float = 100.0,
    ) -> None:
        """
        Add an existing provider instance to the router.
        
        Args:
            name: Friendly name for this gateway
            provider: Initialized BaseProvider instance
            priority: Lower number = higher priority
            enabled: Whether gateway is initially enabled
            max_load_percent: Max % of requests this gateway handles
        """
        self.router.add_provider(
            name=name,
            provider=provider,
            priority=priority,
            enabled=enabled,
            max_load_percent=max_load_percent,
        )
        
        if not self._default_gateway or priority == 0:
            self._default_gateway = name
        
        logger.info(
            f"Gateway '{name}' added (priority={priority}, "
            f"enabled={enabled}, load_limit={max_load_percent}%)"
        )
    
    def enable_gateway(self, name: str) -> None:
        """Enable a gateway for routing."""
        self.router.enable_provider(name)
    
    def disable_gateway(self, name: str) -> None:
        """Temporarily disable a gateway."""
        self.router.disable_provider(name)
    
    def get_gateway(self, name: str) -> Optional[BaseProvider]:
        """Get a specific gateway by name."""
        return self.router.get_provider(name)
    
    # =========================================================================
    # Transactions with Multi-Gateway Support
    # =========================================================================
    
    async def charge(
        self,
        amount: float,
        email: str,
        currency: str = "NGN",
        strategy: Optional[str] = None,
        max_retries: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute charge with automatic failover across gateways.
        
        Args:
            amount: Transaction amount
            email: Customer email
            currency: Currency code (NGN, USD, etc)
            strategy: "primary_fallback" (default) or "load_balance"
            max_retries: Number of gateways to try (default: num_gateways)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            {
                "success": True,
                "provider": "paystack",
                "response": {...}
            }
        
        Raises:
            GatewayUnavailableError: All gateways failed
        """
        max_retries = max_retries or len(self.router.routes)
        
        try:
            result = await self.router.charge(
                amount=amount,
                email=email,
                currency=currency,
                strategy=strategy,
                max_retries=max_retries,
                **kwargs
            )
            return result
        except GatewayUnavailableError as e:
            logger.error(f"Charge failed: {e}")
            raise
    
    async def verify_transaction(
        self,
        transaction_ref: str,
        gateway_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Verify transaction status.
        
        Args:
            transaction_ref: Transaction reference
            gateway_name: Specific gateway to verify on (auto if None)
            **kwargs: Additional parameters
        
        Returns:
            {
                "success": True,
                "provider": "paystack",
                "response": {...}
            }
        """
        try:
            result = await self.router.verify_transaction(
                transaction_ref=transaction_ref,
                provider_name=gateway_name,
                **kwargs
            )
            return result
        except GatewayUnavailableError as e:
            logger.error(f"Verification failed: {e}")
            raise
    
    async def refund(
        self,
        transaction_ref: str,
        amount: Optional[float] = None,
        gateway_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refund a transaction.
        
        Args:
            transaction_ref: Transaction reference
            amount: Refund amount (full refund if None)
            gateway_name: Specific gateway to refund on (auto if None)
            **kwargs: Additional parameters
        
        Returns:
            {
                "success": True,
                "provider": "paystack",
                "response": {...}
            }
        """
        try:
            result = await self.router.refund(
                transaction_ref=transaction_ref,
                amount=amount,
                provider_name=gateway_name,
                **kwargs
            )
            return result
        except GatewayUnavailableError as e:
            logger.error(f"Refund failed: {e}")
            raise
    
    # =========================================================================
    # Health & Monitoring
    # =========================================================================
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all gateways."""
        return self.router.get_health_status()
    
    def get_gateway_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific gateway."""
        return self.router.get_provider_stats(name)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all gateways."""
        return self.router.get_all_stats()
    
    def print_health_report(self) -> None:
        """Print formatted health report."""
        health = self.get_health_status()
        
        print("\n" + "=" * 80)
        print("MULTI-GATEWAY HEALTH REPORT")
        print("=" * 80)
        print(f"Timestamp: {health['timestamp']}")
        print(f"Healthy: {health['healthy_count']}/{health['total_count']}\n")
        
        for name, stats in health["providers"].items():
            health_emoji = {
                "healthy": "✓ HEALTHY",
                "degraded": "⚠ DEGRADED",
                "unavailable": "✗ UNAVAILABLE",
            }.get(stats["health"], "? UNKNOWN")
            
            print(f"  {name.upper()}")
            print(f"    Status: {health_emoji}")
            print(f"    Priority: {stats['priority']}")
            print(f"    Enabled: {stats['enabled']}")
            print(f"    Requests: {stats['total_requests']} "
                  f"({stats['successful_requests']} ok, {stats['failed_requests']} failed)")
            print(f"    Error Rate: {stats['error_rate_percent']}%")
            print(f"    Consecutive Failures: {stats['consecutive_failures']}")
            print(f"    Consecutive Successes: {stats['consecutive_successes']}")
            if stats['last_failure']:
                print(f"    Last Failure: {stats['last_failure']}")
            print()
    
    def reset_stats(self, gateway_name: Optional[str] = None) -> None:
        """Reset statistics for gateway(s)."""
        self.router.reset_stats(provider_name=gateway_name)
        if gateway_name:
            logger.info(f"Stats reset for gateway: {gateway_name}")
        else:
            logger.info("Stats reset for all gateways")
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    async def close_all(self) -> None:
        """Close all gateway connections."""
        for route in self.router.routes.values():
            if hasattr(route.provider, '_client'):
                await route.provider._client.aclose()
                logger.info(f"Closed connection for {route.name}")
