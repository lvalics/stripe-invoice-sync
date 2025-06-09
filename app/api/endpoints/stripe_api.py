"""
Stripe-related API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.crud import InvoiceCRUD
from app.db.models import ProcessingStatus, InvoiceType

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


@router.get("/invoices")
async def get_invoices(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date for invoice search (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date for invoice search (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Invoice status filter"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    limit: int = Query(100, description="Maximum number of invoices to return")
):
    """Fetch invoices from Stripe for the specified date range"""
    try:
        stripe_service = request.app.state.stripe_service
        
        # Parse dates if provided
        if start_date:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_datetime = datetime.now().replace(day=1)  # Default to start of current month
            
        if end_date:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        else:
            end_datetime = datetime.now()  # Default to now
        
        # Fetch invoices
        invoices = await stripe_service.fetch_invoices(
            start_date=start_datetime,
            end_date=end_datetime,
            status=status,
            limit=limit,
            customer_id=customer_id
        )
        
        # Transform to response format for frontend
        response_invoices = []
        for inv in invoices:
            customer = inv.get("customer", {})
            customer_obj = inv.get("customer_object", {})
            
            # Extract customer info
            if isinstance(customer, str):
                customer_id = customer
                customer_name = customer_obj.get("name", "") if customer_obj else ""
                customer_email = customer_obj.get("email", "") if customer_obj else ""
            elif isinstance(customer, dict):
                customer_id = customer.get("id", "")
                customer_name = customer.get("name", "")
                customer_email = customer.get("email", "")
            else:
                customer_id = ""
                customer_name = ""
                customer_email = ""
                
            # Check for refunds
            amount_paid = inv.get("amount_paid", 0)
            amount_remaining = inv.get("amount_remaining", 0)
            total = inv.get("total", 0)
            
            # Determine display status
            display_status = inv.get("status", "")
            if display_status == "paid" and amount_paid < total:
                display_status = "partially_refunded"
            elif display_status == "paid" and amount_paid == 0:
                display_status = "refunded"
                
            response_invoices.append({
                "id": inv["id"],
                "number": inv.get("number"),
                "customer": customer_id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "amount_paid": amount_paid,
                "amount_total": total,
                "currency": inv.get("currency", "").lower(),
                "status": display_status,
                "original_status": inv.get("status", ""),
                "created": inv["created"],
                "period_start": inv.get("period_start", inv["created"]),
                "period_end": inv.get("period_end", inv["created"]),
                "lines": []  # Add line items if needed
            })
        
        return response_invoices
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {str(e)}")


@router.get("/charges")
async def get_charges(
    request: Request,
    start_date: Optional[str] = Query(None, description="Start date for charge search (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date for charge search (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Charge status filter"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    limit: int = Query(100, description="Maximum number of charges to return")
):
    """Fetch charges/orders from Stripe for the specified date range"""
    try:
        stripe_service = request.app.state.stripe_service
        
        # Parse dates if provided
        if start_date:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_datetime = datetime.now().replace(day=1)  # Default to start of current month
            
        if end_date:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        else:
            end_datetime = datetime.now()  # Default to now
        
        # Fetch charges
        charges = await stripe_service.fetch_charges(
            start_date=start_datetime,
            end_date=end_datetime,
            status=status,
            limit=limit,
            customer_id=customer_id
        )
        
        # Transform to response format for frontend
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
                
            # Check refund status
            amount = charge.get("amount", 0)
            amount_refunded = charge.get("amount_refunded", 0)
            refunded = charge.get("refunded", False)
            
            # Determine display status
            display_status = charge.get("status", "")
            if refunded:
                display_status = "refunded"
            elif amount_refunded > 0 and amount_refunded < amount:
                display_status = "partially_refunded"
            elif display_status == "succeeded":
                display_status = "paid"
                
            response_charges.append({
                "id": charge["id"],
                "customer": customer_id or "",
                "customer_name": customer_name or "",
                "customer_email": customer_email or "",
                "amount": amount,
                "amount_refunded": amount_refunded,
                "currency": charge.get("currency", "").lower(),
                "status": display_status,
                "original_status": charge.get("status", ""),
                "refunded": refunded,
                "created": charge["created"],
                "description": charge.get("description"),
                "source_type": "charge"
            })
        
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


class ProcessInvoicesRequest(BaseModel):
    invoice_ids: List[str]
    provider: str


@router.post("/process-invoices")
async def process_invoices(
    request: Request,
    data: ProcessInvoicesRequest,
    db: Session = Depends(get_db)
):
    """Process selected Stripe invoices through the specified provider"""
    try:
        stripe_service = request.app.state.stripe_service
        providers = request.app.state.providers
        
        if data.provider not in providers:
            raise HTTPException(status_code=400, detail=f"Provider {data.provider} not found or not enabled")
        
        provider = providers[data.provider]
        
        results = {
            "total": len(data.invoice_ids),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        for invoice_id in data.invoice_ids:
            try:
                # Fetch invoice from Stripe
                invoice = await stripe_service.get_invoice_by_id(invoice_id)
                
                # Convert to our internal format
                from app.models import InvoiceData, CustomerData, AddressData, ItemData
                
                # Extract customer data
                customer_obj = invoice.get("customer_object", {})
                customer_id = invoice.get("customer")
                if isinstance(customer_id, dict):
                    customer_id = customer_id.get("id", "")
                    
                customer_data = CustomerData(
                    stripe_customer_id=customer_id,
                    name=customer_obj.get("name", "Unknown Customer"),
                    email=customer_obj.get("email", ""),
                    tax_id=customer_obj.get("tax_ids", {}).get("data", [{}])[0].get("value", "") if customer_obj.get("tax_ids", {}).get("data") else "",
                    address=AddressData(
                        line1=customer_obj.get("address", {}).get("line1", ""),
                        line2=customer_obj.get("address", {}).get("line2", ""),
                        city=customer_obj.get("address", {}).get("city", ""),
                        state=customer_obj.get("address", {}).get("state", ""),
                        postal_code=customer_obj.get("address", {}).get("postal_code", ""),
                        country=customer_obj.get("address", {}).get("country", "RO")
                    )
                )
                
                # Extract line items
                items = []
                for line in invoice.get("lines", {}).get("data", []):
                    items.append(ItemData(
                        description=line.get("description", "Service"),
                        quantity=line.get("quantity", 1),
                        unit_price=line.get("price", {}).get("unit_amount", 0) / 100.0,
                        total_price=line.get("amount", 0) / 100.0,
                        currency=line.get("currency", "EUR").upper()
                    ))
                
                invoice_data = InvoiceData(
                    stripe_invoice_id=invoice["id"],
                    invoice_number=invoice.get("number"),
                    amount=invoice.get("amount_paid", 0) / 100.0,
                    currency=invoice.get("currency", "EUR").upper(),
                    customer=customer_data,
                    items=items,
                    invoice_date=datetime.fromtimestamp(invoice["created"]),
                    due_date=datetime.fromtimestamp(invoice.get("due_date", invoice["created"])),
                    metadata=invoice.get("metadata", {})
                )
                
                # Create invoice record
                db_invoice = InvoiceCRUD.create_invoice(
                    db=db,
                    stripe_id=invoice_data.stripe_invoice_id,
                    invoice_type=InvoiceType.STRIPE_INVOICE,
                    provider=data.provider,
                    customer_id=customer_data.stripe_customer_id,
                    customer_email=customer_data.email,
                    customer_tax_id=customer_data.tax_id,
                    amount=invoice_data.amount,
                    currency=invoice_data.currency,
                    invoice_date=invoice_data.invoice_date
                )
                
                # Process through provider
                result = await provider.create_invoice(invoice_data)
                
                if result.success:
                    results["successful"] += 1
                    InvoiceCRUD.update_status(
                        db=db,
                        invoice_id=db_invoice.id,
                        status=ProcessingStatus.COMPLETED,
                        provider_invoice_id=result.provider_invoice_id
                    )
                else:
                    results["failed"] += 1
                    InvoiceCRUD.update_status(
                        db=db,
                        invoice_id=db_invoice.id,
                        status=ProcessingStatus.FAILED,
                        error_message=result.error
                    )
                
                results["details"].append({
                    "invoice_id": invoice_id,
                    "success": result.success,
                    "provider_invoice_id": result.provider_invoice_id,
                    "error": result.error
                })
                
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "invoice_id": invoice_id,
                    "success": False,
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process invoices: {str(e)}")