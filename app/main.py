"""
Main FastAPI application for Stripe Invoice Sync
"""
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any

from app.config import settings
from app.core.provider_factory import ProviderFactory
from app.core.provider_interface import ProviderConfig
from app.api.endpoints import stripe_router, anaf_router, invoice_router, provider_router
from app.services.stripe_service import StripeService, StripeConfig


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global instances
providers: Dict[str, Any] = {}
stripe_service: StripeService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting up Stripe Invoice Sync API")
    
    # Initialize Stripe service
    global stripe_service
    stripe_config = StripeConfig(api_key=settings.stripe_api_key)
    stripe_service = StripeService(stripe_config)
    app.state.stripe_service = stripe_service
    
    # Initialize providers
    global providers
    provider_configs = []
    
    # Add ANAF provider
    if settings.anaf_enabled:
        provider_configs.append(ProviderConfig(**settings.get_anaf_config()))
    
    # Add SmartBill provider
    if settings.smartbill_enabled:
        provider_configs.append(ProviderConfig(**settings.get_smartbill_config()))
    
    providers = ProviderFactory.create_all_providers(provider_configs)
    app.state.providers = providers
    
    logger.info(f"Initialized providers: {list(providers.keys())}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Stripe Invoice Sync API")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stripe_router, prefix="/api/stripe", tags=["Stripe"])
app.include_router(invoice_router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(provider_router, prefix="/api/providers", tags=["Providers"])
app.include_router(anaf_router, prefix="/api/anaf", tags=["ANAF"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "providers": list(providers.keys()),
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "providers": {}
    }
    
    # Check provider status
    for name, provider in providers.items():
        try:
            is_valid = await provider.validate_credentials()
            health_status["providers"][name] = {
                "status": "connected" if is_valid else "disconnected",
                "enabled": True
            }
        except Exception as e:
            health_status["providers"][name] = {
                "status": "error",
                "error": str(e),
                "enabled": True
            }
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )