"""
Factory for creating invoice provider instances
"""
import logging
from typing import Dict, Type, Optional
from app.core.provider_interface import InvoiceProviderInterface, ProviderConfig
from app.providers.anaf_provider import ANAFProvider
from app.providers.smartbill_provider import SmartBillProvider


logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating invoice provider instances"""
    
    # Registry of available providers
    _providers: Dict[str, Type[InvoiceProviderInterface]] = {
        "anaf": ANAFProvider,
        "smartbill": SmartBillProvider,
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[InvoiceProviderInterface]):
        """Register a new provider type"""
        cls._providers[name.lower()] = provider_class
        logger.info(f"Registered provider: {name}")
    
    @classmethod
    def create_provider(cls, config: ProviderConfig) -> Optional[InvoiceProviderInterface]:
        """Create a provider instance from configuration"""
        provider_type = config.name.lower()
        
        if provider_type not in cls._providers:
            logger.error(f"Unknown provider type: {provider_type}")
            return None
        
        if not config.enabled:
            logger.info(f"Provider {config.name} is disabled")
            return None
        
        try:
            provider_class = cls._providers[provider_type]
            provider = provider_class(config)
            logger.info(f"Created provider instance: {config.name}")
            return provider
        except Exception as e:
            logger.error(f"Failed to create provider {config.name}: {str(e)}")
            return None
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider types"""
        return list(cls._providers.keys())
    
    @classmethod
    def create_all_providers(cls, configs: list[ProviderConfig]) -> Dict[str, InvoiceProviderInterface]:
        """Create all enabled providers from configurations"""
        providers = {}
        
        for config in configs:
            provider = cls.create_provider(config)
            if provider:
                providers[config.name] = provider
        
        return providers