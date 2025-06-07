"""
Stripe-related API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel

from app.config import settings


router = APIRouter()


@router.get("/test")
async def test_stripe_connection(request: Request):
    """Test Stripe API connection"""
    try:
        stripe_service = request.app.state.stripe_service
        
        # Try to fetch account info
        import stripe
        stripe.api_key = stripe_service.config.api_key
        
        # Just try to list 1 charge to test connection
        charges = stripe.Charge.list(limit=1)
        
        return {
            "status": "connected",
            "api_key_prefix": stripe_service.config.api_key[:7] if stripe_service.config.api_key else None,
            "test_successful": True,
            "charges_found": len(charges.data)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


class DateRangeParams(BaseModel):
    start_date: date
    end_date: date
    status: Optional[str] = "paid"
    customer_id: Optional[str] = None
    limit: Optional[int] = 100


class StripeInvoiceResponse(BaseModel):
    id: str
    number: Optional[str]
    customer_id: str
    customer_name: str
    customer_email: str
    amount_total: float
    currency: str
    status: str
    created: datetime
    source_type: str = "invoice"


class StripeChargeResponse(BaseModel):
    id: str
    customer_id: Optional[str]
    customer_name: Optional[str]
    customer_email: Optional[str]
    amount: float
    currency: str
    status: str
    created: datetime
    description: Optional[str]
    source_type: str = "charge"


@router.get("/invoices", response_model=List[StripeInvoiceResponse])
async def get_invoices(
    request: Request,
    start_date: date = Query(..., description="Start date for invoice search"),
    end_date: date = Query(..., description="End date for invoice search"),
    status: str = Query("paid", description="Invoice status filter"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    limit: int = Query(100, description="Maximum number of invoices to return")
):
    """Fetch invoices from Stripe for the specified date range"""
    try:
        stripe_service = request.app.state.stripe_service
        
        # Convert dates to datetime
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Fetch invoices
        invoices = await stripe_service.fetch_invoices(
            start_date=start_datetime,
            end_date=end_datetime,
            status=status,
            limit=limit,
            customer_id=customer_id
        )
        
        # Transform to response format
        response_invoices = []
        for inv in invoices:
            customer = inv.get("customer", {})
            if isinstance(customer, str):
                customer = {"id": customer, "name": "", "email": ""}
                
            response_invoices.append(StripeInvoiceResponse(
                id=inv["id"],
                number=inv.get("number"),
                customer_id=customer.get("id", ""),
                customer_name=customer.get("name", ""),
                customer_email=customer.get("email", ""),
                amount_total=inv.get("total", 0) / 100.0,
                currency=inv.get("currency", "").upper(),
                status=inv.get("status", ""),
                created=datetime.fromtimestamp(inv["created"]),
                source_type="invoice"
            ))
        
        return response_invoices
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {str(e)}")


@router.get("/charges", response_model=List[StripeChargeResponse])
async def get_charges(
    request: Request,
    start_date: date = Query(..., description="Start date for charge search"),
    end_date: date = Query(..., description="End date for charge search"),
    status: str = Query("succeeded", description="Charge status filter"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    limit: int = Query(100, description="Maximum number of charges to return")
):
    """Fetch charges/orders from Stripe for the specified date range"""
    try:
        stripe_service = request.app.state.stripe_service
        
        # Convert dates to datetime
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Fetch charges
        charges = await stripe_service.fetch_charges(
            start_date=start_datetime,
            end_date=end_datetime,
            status=status,
            limit=limit,
            customer_id=customer_id
        )
        
        # Transform to response format
        response_charges = []
        for charge in charges:
            customer = charge.get("customer", {})
            customer_name = ""
            customer_email = ""
            customer_id = ""
            
            if isinstance(customer, dict):
                customer_id = customer.get("id", "")
                customer_name = customer.get("name", "")
                customer_email = customer.get("email", "")
            elif isinstance(customer, str):
                customer_id = customer
            
            # Fall back to billing details
            billing = charge.get("billing_details", {})
            if not customer_name:
                customer_name = billing.get("name", "")
            if not customer_email:
                customer_email = billing.get("email", charge.get("receipt_email", ""))
                
            response_charges.append(StripeChargeResponse(
                id=charge["id"],
                customer_id=customer_id or None,
                customer_name=customer_name or None,
                customer_email=customer_email or None,
                amount=charge.get("amount", 0) / 100.0,
                currency=charge.get("currency", "").upper(),
                status=charge.get("status", ""),
                created=datetime.fromtimestamp(charge["created"]),
                description=charge.get("description"),
                source_type="charge"
            ))
        
        return response_charges
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch charges: {str(e)}")


@router.get("/invoice/{invoice_id}")
async def get_invoice_details(request: Request, invoice_id: str):
    """Get detailed information about a specific invoice"""
    try:
        stripe_service = request.app.state.stripe_service
        invoice = await stripe_service.get_invoice_by_id(invoice_id)
        return invoice
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Invoice not found: {str(e)}")


@router.get("/charge/{charge_id}")
async def get_charge_details(request: Request, charge_id: str):
    """Get detailed information about a specific charge"""
    try:
        stripe_service = request.app.state.stripe_service
        charge = await stripe_service.get_charge_by_id(charge_id)
        return charge
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Charge not found: {str(e)}")