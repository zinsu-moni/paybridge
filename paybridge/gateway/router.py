"""
Multi-gateway routing and fallback system.
Routes payment requests to optimal provider with fallback support.
"""

import random
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, timedelta
from ..core.config import logger
from ..provider.base import BaseProvider
from ..expections import ProviderUnavailable


class RoutingStrategy(Enum):
    """Gateway routing strategies."""
    ROUND_ROBIN = "round_robin"      # Distribute evenly
    LEAST_LOADED = "least_loaded"    # Route to least busy provider
    RANDOM = "random"                 # Random selection
    PRIORITY = "priority"             # Use preferred provider, fallback on error
    WEIGHTED = "weighted"             # Based on provider weight/success rate


class GatewayRouter:
    """
    Routes payment requests across multiple gateways with:
    - Multiple routing strategies
    - Automatic fallback on failure
    - Load balancing
    - Provider health tracking
    - Dynamic provider management
    """
    
    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
        max_retries: int = 2,
        health_check_interval: int = 300,  # 5 minutes
    ):
        """
        Args:
            strategy: Routing strategy to use
            max_retries: Max fallback attempts per request
            health_check_interval: Seconds between provider health checks
        """
        self.strategy = strategy
        self.max_retries = max_retries
        self.health_check_interval = health_check_interval
        
        self._providers: Dict[str, BaseProvider] = {}
        self._provider_weights: Dict[str, float] = {}
        self._provider_stats: Dict[str, Dict[str, Any]] = {}
        self._provider_priority: Dict[str, int] = {}  # Maps provider name to priority
        self._last_round_robin_idx = 0
        self._last_health_check: Optional[datetime] = None
    
    def register_provider(
        self,
        name: str,
        provider: BaseProvider,
        weight: float = 1.0,
        priority: int = 0,
    ) -> None:
        """
        Register a payment provider.
        
        Args:
            name: Provider identifier (e.g., 'paystack', 'flutterwave')
            provider: BaseProvider instance
            weight: Load balancing weight (higher = more requests)
            priority: Priority order (lower = higher priority)
        """
        self._providers[name] = provider
        self._provider_weights[name] = weight
        self._provider_priority[name] = priority
        self._provider_stats[name] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "last_error": None,
            "last_error_time": None,
            "success_rate": 1.0,
        }
        
        logger.info(f"Registered provider: {name} (weight={weight}, priority={priority})")
    
    def unregister_provider(self, name: str) -> None:
        """Unregister a provider."""
        if name in self._providers:
            del self._providers[name]
            del self._provider_weights[name]
            del self._provider_priority[name]
            del self._provider_stats[name]
            logger.info(f"Unregistered provider: {name}")
    
    async def route_request(
        self,
        operation: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Route a request to the best available provider.
        
        Args:
            operation: Method name to call (e.g., 'charge', 'refund')
            *args: Positional arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result from provider operation
            
        Raises:
            ProviderUnavailable: If all providers fail
        """
        if not self._providers:
            raise ProviderUnavailable("No providers registered")
        
        provider_order = self._get_provider_order()
        last_error = None
        
        for attempt, provider_name in enumerate(provider_order[:self.max_retries + 1]):
            try:
                provider = self._providers[provider_name]
                
                # Call the operation
                logger.debug(f"Routing to {provider_name} (attempt {attempt + 1})")
                method = getattr(provider, operation)
                result = await method(*args, **kwargs)
                
                # Record success
                self._record_success(provider_name)
                logger.info(f"Request succeeded on {provider_name}")
                
                return result
                
            except Exception as e:
                last_error = e
                self._record_failure(provider_name, e)
                logger.warning(
                    f"Request failed on {provider_name}: {type(e).__name__}: {e}"
                )
                
                if attempt < self.max_retries:
                    logger.info(f"Attempting fallback provider...")
                    continue
        
        # All providers failed
        error_msg = f"All providers exhausted. Last error: {last_error}"
        logger.error(error_msg)
        raise ProviderUnavailable(error_msg) from last_error
    
    def _get_provider_order(self) -> List[str]:
        """Get provider order based on routing strategy."""
        available = [p for p in self._providers if self._is_provider_healthy(p)]
        
        if not available:
            # If all unhealthy, use all providers as fallback
            available = list(self._providers.keys())
        
        if self.strategy == RoutingStrategy.ROUND_ROBIN:
            return self._route_round_robin(available)
        elif self.strategy == RoutingStrategy.LEAST_LOADED:
            return self._route_least_loaded(available)
        elif self.strategy == RoutingStrategy.RANDOM:
            return self._route_random(available)
        elif self.strategy == RoutingStrategy.WEIGHTED:
            return self._route_weighted(available)
        else:  # PRIORITY
            return self._route_priority(available)
    
    def _route_priority(self, providers: List[str]) -> List[str]:
        """Route by provider priority order."""
        return sorted(providers, key=lambda p: self._provider_priority.get(p, 999))
    
    def _route_round_robin(self, providers: List[str]) -> List[str]:
        """Route using round-robin."""
        rotated = providers[self._last_round_robin_idx:] + providers[:self._last_round_robin_idx]
        self._last_round_robin_idx = (self._last_round_robin_idx + 1) % len(providers)
        return rotated
    
    def _route_least_loaded(self, providers: List[str]) -> List[str]:
        """Route to least loaded providers (by request count)."""
        sorted_providers = sorted(
            providers,
            key=lambda p: self._provider_stats[p]["total_requests"]
        )
        return sorted_providers
    
    def _route_random(self, providers: List[str]) -> List[str]:
        """Route using random selection."""
        shuffled = providers.copy()
        random.shuffle(shuffled)
        return shuffled
    
    def _route_weighted(self, providers: List[str]) -> List[str]:
        """Route based on provider weight and success rate."""
        # Combine weight and success rate
        scores = {}
        for p in providers:
            weight = self._provider_weights[p]
            success_rate = self._provider_stats[p]["success_rate"]
            scores[p] = weight * success_rate
        
        # Sort by score (highest first)
        sorted_providers = sorted(providers, key=lambda p: scores[p], reverse=True)
        return sorted_providers
    
    def _is_provider_healthy(self, provider_name: str) -> bool:
        """Check if provider is healthy (not recently failed)."""
        stats = self._provider_stats[provider_name]
        
        # If no failures, it's healthy
        if stats["last_error_time"] is None:
            return True
        
        # If recent failure (within health check interval), it's unhealthy
        if datetime.now() - stats["last_error_time"] < timedelta(seconds=self.health_check_interval):
            return False
        
        return True
    
    def _record_success(self, provider_name: str) -> None:
        """Record successful request."""
        stats = self._provider_stats[provider_name]
        stats["total_requests"] += 1
        stats["successful_requests"] += 1
        stats["last_error"] = None
        stats["last_error_time"] = None
        stats["success_rate"] = (
            stats["successful_requests"] / stats["total_requests"]
            if stats["total_requests"] > 0 else 1.0
        )
    
    def _record_failure(self, provider_name: str, error: Exception) -> None:
        """Record failed request."""
        stats = self._provider_stats[provider_name]
        stats["total_requests"] += 1
        stats["failed_requests"] += 1
        stats["last_error"] = str(error)
        stats["last_error_time"] = datetime.now()
        stats["success_rate"] = (
            stats["successful_requests"] / stats["total_requests"]
            if stats["total_requests"] > 0 else 0.0
        )
    
    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all providers."""
        return {
            name: {
                **self._provider_stats[name],
                "weight": self._provider_weights[name],
                "healthy": self._is_provider_healthy(name),
            }
            for name in self._providers
        }
    
    def get_provider_status(self) -> str:
        """Get human-readable provider status."""
        status_lines = ["Provider Status:"]
        
        for name in self._provider_priority:
            stats = self._provider_stats[name]
            healthy = self._is_provider_healthy(name)
            status = "✓ HEALTHY" if healthy else "✗ UNHEALTHY"
            
            status_lines.append(
                f"  {name}: {status} | "
                f"Requests: {stats['total_requests']} | "
                f"Success Rate: {stats['success_rate']:.1%}"
            )
        
        return "\n".join(status_lines)
