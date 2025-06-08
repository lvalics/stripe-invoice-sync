"""
Invoice processing API endpoints
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from app.config import settings
from app.core.provider_interface import InvoiceData, ProviderResponse


router = APIRouter()


class ProcessInvoiceRequest(BaseModel):
    source_type: str  # "stripe_invoice" or "stripe_charge"
    source_id: str
    provider: str  # "anaf", "smartbill", etc.
    customer_tax_id: Optional[str] = None
    invoice_number: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BatchProcessRequest(BaseModel):
    invoices: List[ProcessInvoiceRequest]
    provider: str
    async_processing: bool = False


class ProcessingStatus(BaseModel):
    source_id: str
    provider: str
    status: str
    message: Optional[str] = None
    external_id: Optional[str] = None
    errors: List[str] = []
    timestamp: datetime


@router.post("/process", response_model=ProcessingStatus)
async def process_invoice(request: Request, invoice_request: ProcessInvoiceRequest):
    """Process a single Stripe invoice/charge through the specified provider"""
    try:
        stripe_service = request.app.state.stripe_service
        providers = request.app.state.providers

        # Validate provider
        if invoice_request.provider not in providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{invoice_request.provider}' not found or not enabled"
            )
        
        provider = providers[invoice_request.provider]
        
        # Fetch source data from Stripe
        if invoice_request.source_type == "stripe_invoice":
            stripe_data = await stripe_service.get_invoice_by_id(invoice_request.source_id)
            if not stripe_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Stripe invoice not found: {invoice_request.source_id}"
                )
            supplier_info = settings.get_supplier_info()
            invoice_data = stripe_service.convert_invoice_to_standard_format(
                stripe_data,
                supplier_info
            )
        elif invoice_request.source_type == "stripe_charge":
            stripe_data = await stripe_service.get_charge_by_id(invoice_request.source_id)
            if not stripe_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Stripe charge not found: {invoice_request.source_id}"
                )
            invoice_data = stripe_service.convert_charge_to_standard_format(
                stripe_data,
                settings.get_supplier_info()
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source type: {invoice_request.source_type}"
            )
        
        # Override with provided data
        if invoice_request.customer_tax_id:
            invoice_data.customer_tax_id = invoice_request.customer_tax_id
        elif not invoice_data.customer_tax_id:
            # For B2C (individuals without tax ID), use "-" as placeholder
            # This is a legal requirement in Romania - systems need a tax ID field
            # but individuals don't have business tax IDs
            invoice_data.customer_tax_id = "-"
        if invoice_request.invoice_number:
            invoice_data.invoice_number = invoice_request.invoice_number
        if invoice_request.metadata:
            invoice_data.metadata.update(invoice_request.metadata)
        
        # Process through provider
        result = await provider.create_invoice(invoice_data)
        
        return ProcessingStatus(
            source_id=invoice_request.source_id,
            provider=invoice_request.provider,
            status=result.status.value,
            message=result.message,
            external_id=result.external_id,
            errors=result.errors,
            timestamp=result.timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in process_invoice: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process/batch", response_model=List[ProcessingStatus])
async def process_batch(
    request: Request,
    batch_request: BatchProcessRequest,
    background_tasks: BackgroundTasks
):
    """Process multiple invoices through the specified provider"""
    try:
        providers = request.app.state.providers
        
        # Validate provider
        if batch_request.provider not in providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{batch_request.provider}' not found or not enabled"
            )
        
        if batch_request.async_processing:
            # Queue for background processing
            background_tasks.add_task(
                _process_batch_async,
                request.app.state,
                batch_request
            )
            return [
                ProcessingStatus(
                    source_id=inv.source_id,
                    provider=batch_request.provider,
                    status="pending",
                    message="Queued for background processing",
                    timestamp=datetime.now()
                )
                for inv in batch_request.invoices
            ]
        else:
            # Process synchronously
            results = []
            for invoice_req in batch_request.invoices:
                invoice_req.provider = batch_request.provider
                result = await process_invoice(request, invoice_req)
                results.append(result)
            return results
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


@router.get("/status/{source_id}")
async def get_invoice_status(request: Request, source_id: str, provider: str):
    """Get the processing status of an invoice"""
    try:
        providers = request.app.state.providers
        
        if provider not in providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider}' not found"
            )
        
        provider_instance = providers[provider]
        result = await provider_instance.get_invoice_status(source_id)
        
        return ProcessingStatus(
            source_id=source_id,
            provider=provider,
            status=result.status.value,
            message=result.message,
            external_id=result.external_id,
            errors=result.errors,
            timestamp=result.timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/download/{invoice_id}")
async def download_invoice(
    request: Request,
    invoice_id: str,
    provider: str,
    format: str = "pdf"
):
    """Download a processed invoice from the provider"""
    try:
        providers = request.app.state.providers
        
        if provider not in providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider}' not found"
            )
        
        provider_instance = providers[provider]
        
        # First validate credentials to ensure we can connect
        try:
            validation_result = await provider_instance.validate_credentials()
            if not validation_result.get("valid", False):
                raise HTTPException(
                    status_code=401,
                    detail=f"Provider authentication failed: {validation_result.get('message', 'Invalid credentials')}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Provider connection error: {str(e)}"
            )
        
        # Now try to download the invoice
        try:
            content = await provider_instance.download_invoice(invoice_id, format)
            
            if not content:
                raise HTTPException(status_code=404, detail="Invoice not found")
            
            # Return file response
            from fastapi.responses import Response
            media_type = "application/pdf" if format == "pdf" else "application/xml"
            return Response(
                content=content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename=invoice_{invoice_id}.{format}"
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invoice download failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


async def _process_batch_async(app_state, batch_request: BatchProcessRequest):
    """Background task for processing batch invoices"""
    # This would typically update a database with progress
    # For now, it just processes the invoices
    stripe_service = app_state.stripe_service
    providers = app_state.providers
    provider = providers[batch_request.provider]
    
    for invoice_req in batch_request.invoices:
        try:
            # Fetch and convert data
            if invoice_req.source_type == "stripe_invoice":
                stripe_data = await stripe_service.get_invoice_by_id(invoice_req.source_id)
                invoice_data = stripe_service.convert_invoice_to_standard_format(
                    stripe_data,
                    settings.get_supplier_info()
                )
            else:
                stripe_data = await stripe_service.get_charge_by_id(invoice_req.source_id)
                invoice_data = stripe_service.convert_charge_to_standard_format(
                    stripe_data,
                    settings.get_supplier_info()
                )
            
            # Override with provided data
            if invoice_req.customer_tax_id:
                invoice_data.customer_tax_id = invoice_req.customer_tax_id
            elif not invoice_data.customer_tax_id:
                # For B2C (individuals without tax ID), use "-" as placeholder
                # This is a legal requirement in Romania - systems need a tax ID field
                # but individuals don't have business tax IDs
                invoice_data.customer_tax_id = "-"
            if invoice_req.invoice_number:
                invoice_data.invoice_number = invoice_req.invoice_number
            if invoice_req.metadata:
                invoice_data.metadata.update(invoice_req.metadata)
            
            # Process
            await provider.create_invoice(invoice_data)
            
        except Exception as e:
            # Log error and continue
            print(f"Error processing {invoice_req.source_id}: {str(e)}")