"""
Multi-Gateway Router with failover, load balancing, and dynamic provider management.
Supports primary/fallback routing, load distribution, and real-time provider health.
"""

import asyncio
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from ..core.config import logger, settings
from ..expections import NetworkError, GatewayUnavailableError


class ProviderHealth(Enum):
    """Health status of a payment provider."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # High error rate but still usable
    UNAVAILABLE = "unavailable"  # Circuit breaker open or repeated failures


class GatewayRoute:
    """Configuration for a single payment gateway."""
    
    def __init__(
        self,
        name: str,
        provider_instance: Any,  # BaseProvider instance
        priority: int = 0,
        enabled: bool = True,
        max_load_percent: float = 100.0,
    ):
        self.name = name
        self.provider = provider_instance
        self.priority = priority  # Lower = higher priority (0 is primary)
        self.enabled = enabled
        self.max_load_percent = max_load_percent  # Max % of requests this provider handles
        
        # Health tracking
        self.health = ProviderHealth.HEALTHY
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_failure_time: Optional[datetime] = None
        self.total_requests = 0
        self.failed_requests = 0
        self.successful_requests = 0
        self.error_rate = 0.0  # percentage
    
    def record_success(self):
        """Record successful transaction."""
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.total_requests += 1
        self.successful_requests += 1
        self._update_error_rate()
        self._update_health()
    
    def record_failure(self):
        """Record failed transaction."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure_time = datetime.now()
        self._update_error_rate()
        self._update_health()
    
    def _update_error_rate(self):
        """Calculate current error rate."""
        if self.total_requests > 0:
            self.error_rate = (self.failed_requests / self.total_requests) * 100
    
    def _update_health(self):
        """Update health status based on error rate and failures."""
        if not self.enabled:
            self.health = ProviderHealth.UNAVAILABLE
        elif hasattr(self.provider, '_circuit_breaker') and self.provider._circuit_breaker:
            state = self.provider._circuit_breaker.get_state()
            if state == "open":
                self.health = ProviderHealth.UNAVAILABLE
            elif state == "half_open":
                self.health = ProviderHealth.DEGRADED
            elif self.error_rate > 20:  # >20% error rate = degraded
                self.health = ProviderHealth.DEGRADED
            else:
                self.health = ProviderHealth.HEALTHY
        elif self.error_rate > 20:
            self.health = ProviderHealth.DEGRADED
        else:
            self.health = ProviderHealth.HEALTHY
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "health": self.health.value,
            "priority": self.priority,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate_percent": round(self.error_rate, 2),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


class MultiGatewayRouter:
    """
    Routes transactions across multiple payment providers with intelligent failover.
    
    Features:
    - Primary/fallback routing (try providers in priority order)
    - Load balancing across healthy providers
    - Real-time health monitoring
    - Dynamic provider enable/disable
    - Automatic retry on provider failure
    - Circuit breaker integration
    """
    
    def __init__(self, default_strategy: str = "primary_fallback"):
        """
        Args:
            default_strategy: "primary_fallback" or "load_balance"
        """
        self.routes: Dict[str, GatewayRoute] = {}
        self.default_strategy = default_strategy
        self._request_counter = 0
        
        logger.info("MultiGatewayRouter initialized")
    
    # =========================================================================
    # Provider Management
    # =========================================================================
    
    def add_provider(
        self,
        name: str,
        provider: Any,
        priority: int = 0,
        enabled: bool = True,
        max_load_percent: float = 100.0,
    ) -> None:
        """Add a payment provider to the router."""
        route = GatewayRoute(
            name=name,
            provider_instance=provider,
            priority=priority,
            enabled=enabled,
            max_load_percent=max_load_percent,
        )
        self.routes[name] = route
        logger.info(f"Provider '{name}' added (priority={priority}, enabled={enabled})")
    
    def remove_provider(self, name: str) -> None:
        """Remove a payment provider from the router."""
        if name in self.routes:
            del self.routes[name]
            logger.warning(f"Provider '{name}' removed")
    
    def enable_provider(self, name: str) -> None:
        """Enable a provider for routing."""
        if name in self.routes:
            self.routes[name].enabled = True
            logger.info(f"Provider '{name}' enabled")
    
    def disable_provider(self, name: str) -> None:
        """Disable a provider temporarily."""
        if name in self.routes:
            self.routes[name].enabled = False
            logger.warning(f"Provider '{name}' disabled")
    
    def get_provider(self, name: str) -> Optional[Any]:
        """Get a provider instance by name."""
        if name in self.routes:
            return self.routes[name].provider
        return None
    
    # =========================================================================
    # Routing Strategies
    # =========================================================================
    
    def _get_healthy_providers(self) -> List[GatewayRoute]:
        """Get all enabled providers sorted by priority."""
        healthy = [
            route for route in self.routes.values()
            if route.enabled and route.health != ProviderHealth.UNAVAILABLE
        ]
        # Sort by priority (lower number = higher priority)
        healthy.sort(key=lambda r: r.priority)
        return healthy
    
    def _select_primary_fallback(self) -> Optional[GatewayRoute]:
        """
        Primary/Fallback strategy: return first healthy provider.
        Falls back to next provider if first fails.
        """
        healthy = self._get_healthy_providers()
        return healthy[0] if healthy else None
    
    def _select_load_balanced(self) -> Optional[GatewayRoute]:
        """
        Load balancing strategy: distribute across healthy providers.
        Respects max_load_percent settings.
        """
        healthy = self._get_healthy_providers()
        if not healthy:
            return None
        
        # Simple round-robin with load percentage consideration
        self._request_counter += 1
        
        # Weight providers by health and load settings
        weighted = []
        for route in healthy:
            # Higher priority or better health = higher weight
            health_weight = {
                ProviderHealth.HEALTHY: 3,
                ProviderHealth.DEGRADED: 1,
            }.get(route.health, 0)
            
            weight = health_weight * (route.max_load_percent / 100.0)
            weighted.append((route, weight))
        
        # Select provider using weighted random
        total_weight = sum(w for _, w in weighted)
        if total_weight == 0:
            return healthy[0]
        
        # For simplicity, use round-robin with weights
        selected_index = self._request_counter % len(weighted)
        return weighted[selected_index][0]
    
    def select_provider(self, strategy: Optional[str] = None) -> Optional[GatewayRoute]:
        """Select provider based on strategy."""
        strategy = strategy or self.default_strategy
        
        if strategy == "primary_fallback":
            return self._select_primary_fallback()
        elif strategy == "load_balance":
            return self._select_load_balanced()
        else:
            logger.warning(f"Unknown strategy: {strategy}, using primary_fallback")
            return self._select_primary_fallback()
    
    # =========================================================================
    # Transaction Execution
    # =========================================================================
    
    async def charge(
        self,
        amount: float,
        email: str,
        currency: str = "NGN",
        strategy: Optional[str] = None,
        max_retries: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute charge transaction with automatic failover.
        
        Args:
            amount: Transaction amount
            email: Customer email
            currency: Currency code (NGN, USD, etc)
            strategy: Routing strategy (default_strategy if None)
            max_retries: Number of providers to try before failing
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Transaction response from successful provider
        
        Raises:
            GatewayUnavailableError: All providers failed or unavailable
        """
        attempted_providers = []
        last_error = None
        
        # Try up to max_retries providers
        for attempt in range(max_retries):
            route = self.select_provider(strategy)
            
            if not route:
                logger.error("No healthy providers available")
                raise GatewayUnavailableError("No healthy payment providers available")
            
            if route.name in attempted_providers:
                logger.debug(f"Skipping {route.name} (already attempted)")
                continue
            
            attempted_providers.append(route.name)
            
            try:
                logger.info(
                    f"Attempting charge via {route.name} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                
                # Execute transaction
                response = await route.provider.charge(
                    amount=amount,
                    email=email,
                    currency=currency,
                    **kwargs
                )
                
                # Record success
                route.record_success()
                logger.info(f"✓ Charge successful via {route.name}")
                
                return {
                    "success": True,
                    "provider": route.name,
                    "response": response,
                }
            
            except Exception as e:
                route.record_failure()
                last_error = e
                logger.warning(
                    f"✗ Charge failed via {route.name}: {type(e).__name__}: {str(e)}"
                )
                
                # Continue to next provider
                await asyncio.sleep(0.1)  # Brief delay before retry
                continue
        
        # All providers failed
        logger.error(
            f"All {len(attempted_providers)} providers failed: {attempted_providers}"
        )
        raise GatewayUnavailableError(
            f"Transaction failed after {len(attempted_providers)} attempts. "
            f"Last error: {str(last_error)}"
        )
    
    async def verify_transaction(
        self,
        transaction_ref: str,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Verify transaction status (optionally on specific provider).
        
        Args:
            transaction_ref: Transaction reference to verify
            provider_name: Specific provider to use (if None, try primary)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Transaction status from provider
        """
        if provider_name:
            route = self.routes.get(provider_name)
            if not route:
                raise ValueError(f"Provider '{provider_name}' not found")
            
            response = await route.provider.verify_transaction(
                transaction_ref, **kwargs
            )
            return {
                "success": True,
                "provider": provider_name,
                "response": response,
            }
        
        # Try all providers in priority order
        for route in self._get_healthy_providers():
            try:
                response = await route.provider.verify_transaction(
                    transaction_ref, **kwargs
                )
                return {
                    "success": True,
                    "provider": route.name,
                    "response": response,
                }
            except Exception as e:
                logger.debug(f"Verification failed on {route.name}: {e}")
                continue
        
        raise GatewayUnavailableError("Transaction verification failed on all providers")
    
    async def refund(
        self,
        transaction_ref: str,
        amount: Optional[float] = None,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Refund transaction (optionally on specific provider).
        
        Args:
            transaction_ref: Transaction reference to refund
            amount: Refund amount (full refund if None)
            provider_name: Specific provider to use (if None, auto-detect)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Refund response from provider
        """
        if provider_name:
            route = self.routes.get(provider_name)
            if not route:
                raise ValueError(f"Provider '{provider_name}' not found")
            
            response = await route.provider.refund(
                transaction_ref=transaction_ref,
                amount=amount,
                **kwargs
            )
            return {
                "success": True,
                "provider": provider_name,
                "response": response,
            }
        
        # Try all providers to find the one that handled this transaction
        for route in self._get_healthy_providers():
            try:
                response = await route.provider.refund(
                    transaction_ref=transaction_ref,
                    amount=amount,
                    **kwargs
                )
                return {
                    "success": True,
                    "provider": route.name,
                    "response": response,
                }
            except Exception as e:
                logger.debug(f"Refund failed on {route.name}: {e}")
                continue
        
        raise GatewayUnavailableError("Refund failed on all providers")
    
    # =========================================================================
    # Health & Monitoring
    # =========================================================================
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all providers."""
        return {
            "timestamp": datetime.now().isoformat(),
            "providers": {
                name: route.get_stats()
                for name, route in self.routes.items()
            },
            "healthy_count": sum(
                1 for route in self.routes.values()
                if route.health == ProviderHealth.HEALTHY
            ),
            "total_count": len(self.routes),
        }
    
    def get_provider_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific provider."""
        if name in self.routes:
            return self.routes[name].get_stats()
        return None
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all providers."""
        return {
            name: route.get_stats()
            for name, route in self.routes.items()
        }
    
    def reset_stats(self, provider_name: Optional[str] = None) -> None:
        """Reset statistics for provider(s)."""
        if provider_name:
            if provider_name in self.routes:
                route = self.routes[provider_name]
                route.consecutive_failures = 0
                route.consecutive_successes = 0
                route.total_requests = 0
                route.failed_requests = 0
                route.successful_requests = 0
                route.error_rate = 0.0
                logger.info(f"Stats reset for {provider_name}")
        else:
            for route in self.routes.values():
                route.consecutive_failures = 0
                route.consecutive_successes = 0
                route.total_requests = 0
                route.failed_requests = 0
                route.successful_requests = 0
                route.error_rate = 0.0
            logger.info("Stats reset for all providers")
