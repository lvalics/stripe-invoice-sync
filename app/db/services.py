"""Database service layer with transaction support."""
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging
import hashlib
import json

from app.db.database import get_db_context
from app.db.crud import (
    InvoiceCRUD, ProcessingHistoryCRUD, AuditLogCRUD,
    RetryQueueCRUD, InvoiceDocumentCRUD
)
from app.db.models import ProcessingStatus, InvoiceType, ProcessedInvoice
from app.core.provider_interface import InvoiceData, ProviderResponse

logger = logging.getLogger(__name__)


class InvoiceProcessingService:
    """Service layer for invoice processing with transaction support."""
    
    def __init__(self):
        self.invoice_crud = InvoiceCRUD()
        self.history_crud = ProcessingHistoryCRUD()
        self.audit_crud = AuditLogCRUD()
        self.retry_crud = RetryQueueCRUD()
        self.document_crud = InvoiceDocumentCRUD()
    
    def process_invoice_with_duplicate_check(
        self,
        invoice_data: InvoiceData,
        provider: str,
        invoice_type: InvoiceType = InvoiceType.STRIPE_INVOICE
    ) -> Tuple[Optional[ProcessedInvoice], bool]:
        """
        Process an invoice with duplicate detection.
        
        Args:
            invoice_data: Invoice data from Stripe
            provider: Provider name
            invoice_type: Type of invoice
            
        Returns:
            Tuple of (ProcessedInvoice, is_duplicate)
        """
        with get_db_context() as db:
            try:
                # Check for duplicate
                existing = self.invoice_crud.check_duplicate(
                    db, invoice_data.source_id, provider
                )
                
                if existing:
                    # Log duplicate attempt
                    self.audit_crud.create_audit_log(
                        db,
                        event_type="invoice_processing",
                        resource_type="invoice",
                        resource_id=invoice_data.source_id,
                        action="duplicate_detected",
                        description=f"Duplicate invoice detected for provider {provider}",
                        extra_metadata={
                            "provider": provider,
                            "existing_invoice_id": existing.id,
                            "status": existing.status
                        }
                    )
                    return existing, True
                
                # Create new invoice record
                invoice = self.invoice_crud.create_invoice(
                    db,
                    stripe_id=invoice_data.source_id,
                    invoice_type=invoice_type,
                    provider=provider,
                    customer_id=invoice_data.customer_id,
                    customer_email=invoice_data.customer_email,
                    amount=invoice_data.total,
                    currency=invoice_data.currency,
                    invoice_date=invoice_data.invoice_date,
                    customer_tax_id=invoice_data.customer_tax_id,
                    extra_metadata={
                        "customer_name": invoice_data.customer_name,
                        "lines": invoice_data.lines
                    }
                )
                
                # Create initial history entry
                # Convert invoice data to dict with JSON-serializable values
                invoice_dict = invoice_data.dict()
                # Convert datetime to ISO format string
                if 'invoice_date' in invoice_dict and hasattr(invoice_dict['invoice_date'], 'isoformat'):
                    invoice_dict['invoice_date'] = invoice_dict['invoice_date'].isoformat()
                if 'due_date' in invoice_dict and invoice_dict['due_date'] and hasattr(invoice_dict['due_date'], 'isoformat'):
                    invoice_dict['due_date'] = invoice_dict['due_date'].isoformat()
                
                self.history_crud.create_history(
                    db,
                    invoice_id=invoice.id,
                    stripe_id=invoice_data.source_id,
                    provider=provider,
                    action="created",
                    status="success",
                    request_data=invoice_dict
                )
                
                # Audit log
                self.audit_crud.create_audit_log(
                    db,
                    event_type="invoice_processing",
                    resource_type="invoice",
                    resource_id=invoice_data.source_id,
                    action="created",
                    description=f"New invoice created for processing with {provider}",
                    extra_metadata={
                        "provider": provider,
                        "amount": invoice_data.total,
                        "currency": invoice_data.currency
                    }
                )
                
                return invoice, False
                
            except SQLAlchemyError as e:
                logger.error(f"Database error during invoice processing: {e}")
                raise
    
    def update_invoice_status_with_history(
        self,
        invoice_id: int,
        provider_response: ProviderResponse,
        action: str = "process"
    ) -> ProcessedInvoice:
        """
        Update invoice status with full history tracking.
        
        Args:
            invoice_id: Invoice ID
            provider_response: Response from provider
            action: Action that was performed
            
        Returns:
            Updated ProcessedInvoice
        """
        with get_db_context() as db:
            try:
                # Start history record
                history = self.history_crud.create_history(
                    db,
                    invoice_id=invoice_id,
                    stripe_id="",  # Will be filled from invoice
                    provider=provider_response.provider,
                    action=action,
                    status="processing",
                    request_data={"action": action}
                )
                
                # Get invoice to update
                invoice = db.query(ProcessedInvoice).filter(
                    ProcessedInvoice.id == invoice_id
                ).first()
                
                if not invoice:
                    raise ValueError(f"Invoice {invoice_id} not found")
                
                # Update history with stripe_id
                history.stripe_id = invoice.stripe_id
                
                if provider_response.success:
                    # Update invoice status
                    invoice = self.invoice_crud.update_status(
                        db,
                        invoice_id=invoice_id,
                        status=ProcessingStatus.COMPLETED,
                        provider_invoice_id=provider_response.invoice_id
                    )
                    
                    # Complete history
                    self.history_crud.complete_history(
                        db,
                        history_id=history.id,
                        status="success",
                        response_data=provider_response.data
                    )
                    
                    # Audit success
                    self.audit_crud.create_audit_log(
                        db,
                        event_type="invoice_processing",
                        resource_type="invoice",
                        resource_id=invoice.stripe_id,
                        action="completed",
                        description=f"Invoice successfully processed by {provider_response.provider}",
                        extra_metadata={
                            "provider": provider_response.provider,
                            "provider_invoice_id": provider_response.invoice_id
                        }
                    )
                    
                    # Save document if provided
                    if provider_response.data and "xml" in provider_response.data:
                        self._save_invoice_document(
                            db, invoice.id, invoice.stripe_id,
                            provider_response.provider, "xml",
                            provider_response.data["xml"]
                        )
                    
                else:
                    # Update invoice as failed
                    invoice = self.invoice_crud.update_status(
                        db,
                        invoice_id=invoice_id,
                        status=ProcessingStatus.FAILED,
                        error_message=provider_response.message
                    )
                    
                    # Complete history with error
                    self.history_crud.complete_history(
                        db,
                        history_id=history.id,
                        status="failed",
                        error_message=provider_response.error
                    )
                    
                    # Add to retry queue if not at max attempts
                    if invoice.attempts < 3:
                        self.retry_crud.add_to_retry_queue(
                            db,
                            invoice_id=invoice.id,
                            stripe_id=invoice.stripe_id,
                            provider=provider_response.provider,
                            error_message=provider_response.error,
                            retry_after_minutes=30 * invoice.attempts  # Exponential backoff
                        )
                    
                    # Audit failure
                    self.audit_crud.create_audit_log(
                        db,
                        event_type="invoice_processing",
                        resource_type="invoice",
                        resource_id=invoice.stripe_id,
                        action="failed",
                        description=f"Invoice processing failed for {provider_response.provider}",
                        extra_metadata={
                            "provider": provider_response.provider,
                            "error": provider_response.error,
                            "attempts": invoice.attempts
                        }
                    )
                
                return invoice
                
            except SQLAlchemyError as e:
                logger.error(f"Database error during status update: {e}")
                raise
    
    def _save_invoice_document(
        self,
        db: Session,
        invoice_id: int,
        stripe_id: str,
        provider: str,
        document_type: str,
        content: str
    ) -> None:
        """Save invoice document with checksum."""
        try:
            # Calculate checksum
            checksum = hashlib.sha256(content.encode()).hexdigest()
            file_size = len(content.encode())
            
            # Check if document already exists
            existing = self.document_crud.get_document(
                db, invoice_id, document_type, provider
            )
            
            if not existing:
                self.document_crud.save_document(
                    db,
                    invoice_id=invoice_id,
                    stripe_id=stripe_id,
                    provider=provider,
                    document_type=document_type,
                    document_content=content,
                    file_size=file_size,
                    checksum=checksum
                )
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
    
    def get_invoice_full_history(
        self,
        stripe_id: str,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get complete history for an invoice.
        
        Args:
            stripe_id: Stripe invoice ID
            provider: Optional provider filter
            
        Returns:
            Dictionary with invoice details and history
        """
        with get_db_context() as db:
            # Get invoice(s)
            query = db.query(ProcessedInvoice).filter(
                ProcessedInvoice.stripe_id == stripe_id
            )
            
            if provider:
                query = query.filter(ProcessedInvoice.provider == provider)
            
            invoices = query.all()
            
            if not invoices:
                return {"error": "Invoice not found"}
            
            result = []
            for invoice in invoices:
                # Get processing history
                history = self.history_crud.get_invoice_history(db, invoice.id)
                
                # Get documents
                documents = self.document_crud.get_invoice_documents(db, invoice.id)
                
                # Get retry status
                retry = db.query(RetryQueue).filter(
                    RetryQueue.invoice_id == invoice.id,
                    RetryQueue.active == True
                ).first()
                
                result.append({
                    "invoice": {
                        "id": invoice.id,
                        "stripe_id": invoice.stripe_id,
                        "provider": invoice.provider,
                        "status": invoice.status,
                        "attempts": invoice.attempts,
                        "created_at": invoice.created_at.isoformat(),
                        "processed_at": invoice.processed_at.isoformat() if invoice.processed_at else None,
                        "provider_invoice_id": invoice.provider_invoice_id,
                        "amount": invoice.amount,
                        "currency": invoice.currency
                    },
                    "history": [
                        {
                            "action": h.action,
                            "status": h.status,
                            "started_at": h.started_at.isoformat(),
                            "completed_at": h.completed_at.isoformat() if h.completed_at else None,
                            "duration_ms": h.duration_ms,
                            "error_message": h.error_message
                        }
                        for h in history
                    ],
                    "documents": [
                        {
                            "type": d.document_type,
                            "created_at": d.created_at.isoformat(),
                            "file_size": d.file_size,
                            "checksum": d.checksum
                        }
                        for d in documents
                    ],
                    "retry_status": {
                        "active": True,
                        "retry_count": retry.retry_count,
                        "retry_after": retry.retry_after.isoformat(),
                        "last_error": retry.last_error
                    } if retry else None
                })
            
            return {"invoices": result}
    
    def process_retry_queue(
        self,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Process invoices in the retry queue.
        
        Args:
            provider: Optional provider filter
            
        Returns:
            List of retry results
        """
        results = []
        
        with get_db_context() as db:
            # Get ready retries
            retries = self.retry_crud.get_ready_retries(db, provider)
            
            for retry in retries:
                # Get invoice
                invoice = db.query(ProcessedInvoice).filter(
                    ProcessedInvoice.id == retry.invoice_id
                ).first()
                
                if invoice:
                    results.append({
                        "retry_id": retry.id,
                        "invoice_id": invoice.id,
                        "stripe_id": invoice.stripe_id,
                        "provider": invoice.provider,
                        "retry_count": retry.retry_count,
                        "status": "pending_retry"
                    })
                    
                    # Update invoice status to RETRY
                    invoice.status = ProcessingStatus.RETRY
                    db.commit()
            
        return results
    
    def get_processing_stats(
        self,
        provider: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Args:
            provider: Optional provider filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Processing statistics
        """
        with get_db_context() as db:
            query = db.query(ProcessedInvoice)
            
            if provider:
                query = query.filter(ProcessedInvoice.provider == provider)
            
            if start_date:
                query = query.filter(ProcessedInvoice.created_at >= start_date)
            
            if end_date:
                query = query.filter(ProcessedInvoice.created_at <= end_date)
            
            invoices = query.all()
            
            # Calculate statistics
            total = len(invoices)
            completed = sum(1 for i in invoices if i.status == ProcessingStatus.COMPLETED)
            failed = sum(1 for i in invoices if i.status == ProcessingStatus.FAILED)
            pending = sum(1 for i in invoices if i.status == ProcessingStatus.PENDING)
            retry = sum(1 for i in invoices if i.status == ProcessingStatus.RETRY)
            
            # Success rate
            success_rate = (completed / total * 100) if total > 0 else 0
            
            # Average attempts for completed
            completed_invoices = [i for i in invoices if i.status == ProcessingStatus.COMPLETED]
            avg_attempts = sum(i.attempts for i in completed_invoices) / len(completed_invoices) if completed_invoices else 0
            
            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "pending": pending,
                "retry": retry,
                "success_rate": round(success_rate, 2),
                "average_attempts": round(avg_attempts, 2),
                "provider": provider,
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }


# Create singleton instance
invoice_processing_service = InvoiceProcessingService()