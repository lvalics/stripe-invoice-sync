"""
ANAF-specific API endpoints
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from pydantic import BaseModel


router = APIRouter()


class CompanyInfo(BaseModel):
    cui: str
    name: str
    address: str
    registration_number: Optional[str]
    phone: Optional[str]
    vat_payer: bool
    vat_registration_date: Optional[str]
    status: Optional[str]


@router.get("/company/{cui}", response_model=CompanyInfo)
async def get_company_info(request: Request, cui: str):
    """Get company information from ANAF by CUI/Tax ID"""
    # import logging
    # logger = logging.getLogger(__name__)
    # logger.info(f"Received request for CUI: {cui}")
    
    providers = request.app.state.providers
    
    # Try to find a provider that supports company lookup
    anaf_provider = providers.get("anaf")
    if not anaf_provider:
        raise HTTPException(
            status_code=503,
            detail="ANAF provider not available"
        )
    
    try:
        company_data = await anaf_provider.get_company_info(cui)
        
        if not company_data:
            # logger.info(f"No data found for CUI: {cui}")
            raise HTTPException(
                status_code=404,
                detail=f"Company with CUI {cui} not found"
            )
        
        return CompanyInfo(
            cui=company_data["cui"],
            name=company_data["name"],
            address=company_data["address"],
            registration_number=company_data.get("registration_number"),
            phone=company_data.get("phone"),
            vat_payer=company_data.get("vat_payer", False),
            vat_registration_date=company_data.get("vat_registration_date"),
            status=company_data.get("status")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a connection error
        error_msg = str(e).lower()
        if "connection" in error_msg or "timeout" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"ANAF service connection error: {str(e)}"
            )
        elif "invalid cui" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch company info: {str(e)}"
            )


@router.post("/validate-cui")
async def validate_cui(cui: str):
    """Validate Romanian CUI format"""
    # Remove RO prefix if present
    cui_clean = cui.upper().replace("RO", "").strip()
    
    # Check if it's numeric
    if not cui_clean.isdigit():
        return {
            "valid": False,
            "error": "CUI must contain only digits",
            "formatted": None
        }
    
    # Check length (2-10 digits)
    if len(cui_clean) < 2 or len(cui_clean) > 10:
        return {
            "valid": False,
            "error": "CUI must be between 2 and 10 digits",
            "formatted": None
        }
    
    return {
        "valid": True,
        "error": None,
        "formatted": f"RO{cui_clean}"
    }