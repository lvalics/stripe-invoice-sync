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
from app.db.models import ProcessingStatus, InvoiceType, ProcessedInvoice
import logging

from app.config import settings

logger = logging.getLogger(__name__)


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


class CheckProcessedRequest(BaseModel):
    invoice_ids: List[str]


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
                from app.core.provider_interface import InvoiceData
                
                # Extract customer data
                # When we expand customer in get_invoice_by_id, it returns the full customer object
                customer = invoice.get("customer")
                if isinstance(customer, dict):
                    customer_obj = customer
                    customer_id = customer.get("id", "")
                    logger.debug(f"Invoice {invoice_id}: Customer expanded - email: {customer_obj.get('email')}, name: {customer_obj.get('name')}")
                else:
                    # If customer is just a string ID, we don't have the full object
                    customer_obj = {}
                    customer_id = customer if customer else ""
                    logger.warning(f"Invoice {invoice_id}: Customer not expanded, only ID available: {customer_id}")
                
                # Extract customer tax ID
                customer_tax_id = ""
                if customer_obj.get("tax_ids", {}).get("data"):
                    customer_tax_id = customer_obj["tax_ids"]["data"][0].get("value", "")
                
                # Extract customer address
                customer_address = None
                if customer_obj.get("address"):
                    customer_address = {
                        "line1": customer_obj["address"].get("line1", ""),
                        "line2": customer_obj["address"].get("line2", ""),
                        "city": customer_obj["address"].get("city", ""),
                        "state": customer_obj["address"].get("state", ""),
                        "postal_code": customer_obj["address"].get("postal_code", ""),
                        "country": customer_obj["address"].get("country", "RO")
                    }
                
                # Extract line items
                lines = []
                for line in invoice.get("lines", {}).get("data", []):
                    # Get the price - it might be in different formats
                    unit_price = 0.0
                    if isinstance(line.get("price"), dict):
                        unit_price = line["price"].get("unit_amount", 0) / 100.0
                    elif line.get("unit_amount"):
                        unit_price = line.get("unit_amount", 0) / 100.0
                    elif line.get("amount"):
                        # If no unit price, calculate from total amount and quantity
                        quantity = line.get("quantity", 1)
                        unit_price = (line.get("amount", 0) / 100.0) / quantity if quantity > 0 else 0.0
                    
                    total_price = line.get("amount", 0) / 100.0
                    
                    # Adjust prices based on VAT inclusion
                    if settings.stripe_prices_include_tax:
                        # Extract VAT from the prices
                        unit_price = unit_price / (1 + settings.default_tax_rate / 100)
                        total_price = total_price / (1 + settings.default_tax_rate / 100)
                    
                    lines.append({
                        "description": line.get("description", "Service"),
                        "quantity": line.get("quantity", 1),
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "currency": line.get("currency", "EUR").upper(),
                        "tax_rate": settings.default_tax_rate
                    })
                
                # Calculate totals
                amount_paid = invoice.get("amount_paid", 0) / 100.0
                amount_total = invoice.get("total", 0) / 100.0
                
                # Handle VAT calculation based on whether Stripe prices include tax
                if settings.stripe_prices_include_tax:
                    # Prices include tax - need to extract the base amount
                    subtotal = amount_total / (1 + settings.default_tax_rate / 100)
                    tax_amount = amount_total - subtotal
                else:
                    # Prices don't include tax - need to add tax
                    subtotal = amount_total
                    tax_amount = subtotal * (settings.default_tax_rate / 100)
                    amount_total = subtotal + tax_amount
                
                invoice_data = InvoiceData(
                    source_type="stripe_invoice",
                    source_id=invoice["id"],
                    source_data=invoice,
                    invoice_number=invoice.get("number"),
                    invoice_date=datetime.fromtimestamp(invoice["created"]),
                    due_date=datetime.fromtimestamp(invoice.get("due_date", invoice["created"])),
                    currency=invoice.get("currency", "EUR").upper(),
                    customer_id=customer_id,
                    customer_name=customer_obj.get("name", "Unknown Customer"),
                    customer_email=customer_obj.get("email", ""),
                    customer_tax_id=customer_tax_id,
                    customer_address=customer_address,
                    customer_country=customer_address.get("country", "RO") if customer_address else "RO",
                    supplier_name=settings.company_name,
                    supplier_tax_id=settings.company_cui,
                    supplier_address={
                        "street": settings.company_address_street,
                        "city": settings.company_address_city,
                        "county": settings.company_address_county,
                        "postal_code": settings.company_address_postal,
                        "country": settings.company_address_country
                    },
                    supplier_registration=settings.company_registration,
                    lines=lines,
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    total=amount_total,
                    amount_paid=amount_paid,
                    tax_rate=settings.default_tax_rate,
                    tax_breakdown=[{
                        "rate": settings.default_tax_rate,
                        "base": subtotal,
                        "amount": tax_amount
                    }],
                    metadata=invoice.get("metadata", {})
                )
                
                # Check if invoice already processed with this provider
                existing_invoice = InvoiceCRUD.check_duplicate(
                    db=db,
                    stripe_id=invoice_data.source_id,
                    provider=data.provider
                )
                
                if existing_invoice:
                    if existing_invoice.status == ProcessingStatus.COMPLETED:
                        results["details"].append({
                            "invoice_id": invoice_id,
                            "success": True,
                            "provider_invoice_id": existing_invoice.provider_invoice_id,
                            "error": None,
                            "message": "Invoice already processed"
                        })
                        results["successful"] += 1
                        continue
                    else:
                        # Update existing record
                        db_invoice = existing_invoice
                else:
                    # Create new invoice record
                    db_invoice = InvoiceCRUD.create_invoice(
                        db=db,
                        stripe_id=invoice_data.source_id,
                        invoice_type=InvoiceType.STRIPE_INVOICE,
                        provider=data.provider,
                        customer_id=invoice_data.customer_id,
                        customer_email=invoice_data.customer_email,
                        customer_tax_id=invoice_data.customer_tax_id,
                        amount=invoice_data.amount_paid,
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
                        provider_invoice_id=result.external_id
                    )
                else:
                    results["failed"] += 1
                    error_msg = result.errors[0] if result.errors else "Unknown error"
                    InvoiceCRUD.update_status(
                        db=db,
                        invoice_id=db_invoice.id,
                        status=ProcessingStatus.FAILED,
                        error_message=error_msg
                    )
                
                results["details"].append({
                    "invoice_id": invoice_id,
                    "success": result.success,
                    "provider_invoice_id": result.external_id,
                    "error": result.errors[0] if result.errors else None
                })
                
            except Exception as e:
                import traceback
                logger.error(f"Error processing invoice {invoice_id}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                results["failed"] += 1
                results["details"].append({
                    "invoice_id": invoice_id,
                    "success": False,
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process invoices: {str(e)}")


@router.post("/check-processed")
async def check_processed_invoices(
    data: ProcessInvoicesRequest,
    db: Session = Depends(get_db)
):
    """Check which invoices have already been processed with a specific provider"""
    processed = {}
    
    logger.debug(f"Checking processed status for {len(data.invoice_ids)} invoices with provider {data.provider}")
    
    for invoice_id in data.invoice_ids:
        existing = InvoiceCRUD.check_duplicate(
            db=db,
            stripe_id=invoice_id,
            provider=data.provider
        )
        if existing:
            logger.debug(f"Invoice {invoice_id} found: status={existing.status}, provider_id={existing.provider_invoice_id}")
            processed[invoice_id] = {
                "processed": True,
                "status": existing.status,
                "provider_invoice_id": existing.provider_invoice_id,
                "processed_at": existing.processed_at.isoformat() if existing.processed_at else None,
                "provider": existing.provider
            }
        else:
            processed[invoice_id] = {
                "processed": False,
                "status": None,
                "provider_invoice_id": None,
                "processed_at": None,
                "provider": None
            }
    
    return processed


@router.post("/check-all-processed")
async def check_all_processed_invoices(
    data: CheckProcessedRequest,
    db: Session = Depends(get_db)
):
    """Check which invoices have been processed by ANY provider"""
    from sqlalchemy import or_
    
    processed = {}
    
    logger.info(f"Checking all processed status for {len(data.invoice_ids)} invoices")
    
    # Get all processed invoices for these IDs
    all_processed = db.query(ProcessedInvoice).filter(
        ProcessedInvoice.stripe_id.in_(data.invoice_ids)
    ).all()
    
    logger.info(f"Found {len(all_processed)} processed records")
    for p in all_processed:
        logger.info(f"  - {p.stripe_id}: {p.provider} - {p.status}")
    
    # Group by invoice ID
    for invoice_id in data.invoice_ids:
        invoice_providers = [p for p in all_processed if p.stripe_id == invoice_id]
        
        if invoice_providers:
            # Get all providers that processed this invoice
            providers_info = []
            for p in invoice_providers:
                providers_info.append({
                    "provider": p.provider,
                    "status": p.status,
                    "provider_invoice_id": p.provider_invoice_id,
                    "processed_at": p.processed_at.isoformat() if p.processed_at else None
                })
            
            processed[invoice_id] = {
                "processed": True,
                "providers": providers_info
            }
        else:
            processed[invoice_id] = {
                "processed": False,
                "providers": []
            }
    
    return processed