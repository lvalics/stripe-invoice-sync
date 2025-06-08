"""
Provider management API endpoints
"""
from fastapi import APIRouter, Request
from typing import List, Dict, Any
from pydantic import BaseModel


router = APIRouter()


class ProviderInfo(BaseModel):
    name: str
    enabled: bool
    authenticated: bool
    capabilities: List[str]
    configuration: Dict[str, Any]


@router.get("/", response_model=List[ProviderInfo])
async def list_providers(request: Request):
    """List all configured providers and their status"""
    providers = request.app.state.providers
    provider_list = []
    
    for name, provider in providers.items():
        # Check authentication status
        try:
            auth_result = await provider.validate_credentials()
            is_authenticated = auth_result.get("valid", False)
        except:
            is_authenticated = False
        
        # Determine capabilities
        capabilities = ["create_invoice", "get_status", "download"]
        if hasattr(provider, "get_company_info") and provider.get_company_info:
            capabilities.append("company_lookup")
        if await provider.supports_batch_processing():
            capabilities.append("batch_processing")
        
        provider_list.append(ProviderInfo(
            name=name,
            enabled=True,
            authenticated=is_authenticated,
            capabilities=capabilities,
            configuration={
                "auth_type": provider.config.auth_type,
                "options": provider.config.options
            }
        ))
    
    return provider_list


@router.get("/{provider_name}/validate")
async def validate_provider(request: Request, provider_name: str):
    """Validate provider credentials"""
    providers = request.app.state.providers
    
    if provider_name not in providers:
        return {
            "provider": provider_name,
            "valid": False,
            "error": "Provider not found or not enabled"
        }
    
    try:
        provider = providers[provider_name]
        is_valid = await provider.validate_credentials()
        return {
            "provider": provider_name,
            "valid": is_valid,
            "error": None if is_valid else "Invalid credentials"
        }
    except Exception as e:
        return {
            "provider": provider_name,
            "valid": False,
            "error": str(e)
        }