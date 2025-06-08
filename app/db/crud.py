"""CRUD operations for database models."""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from app.db.models import (
    ProcessedInvoice, ProcessingHistory, AuditLog, 
    RetryQueue, InvoiceDocument, ProcessingStatus,
    InvoiceType
)

logger = logging.getLogger(__name__)


class InvoiceCRUD:
    """CRUD operations for invoice processing."""
    
    @staticmethod
    def check_duplicate(
        db: Session, 
        stripe_id: str, 
        provider: str
    ) -> Optional[ProcessedInvoice]:
        """
        Check if an invoice has already been processed for a provider.
        
        Args:
            db: Database session
            stripe_id: Stripe invoice or charge ID
            provider: Provider name
            
        Returns:
            ProcessedInvoice if exists, None otherwise
        """
        return db.query(ProcessedInvoice).filter(
            and_(
                ProcessedInvoice.stripe_id == stripe_id,
                ProcessedInvoice.provider == provider
            )
        ).first()
    
    @staticmethod
    def create_invoice(
        db: Session,
        stripe_id: str,
        invoice_type: InvoiceType,
        provider: str,
        customer_id: str,
        customer_email: str,
        amount: float,
        currency: str,
        invoice_date: datetime,
        customer_tax_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessedInvoice:
        """
        Create a new invoice record.
        
        Args:
            db: Database session
            stripe_id: Stripe invoice or charge ID
            invoice_type: Type of invoice (stripe_invoice or stripe_charge)
            provider: Provider name
            customer_id: Customer ID
            customer_email: Customer email
            amount: Invoice amount
            currency: Currency code
            invoice_date: Invoice date
            customer_tax_id: Optional customer tax ID
            extra_metadata: Optional additional metadata
            
        Returns:
            Created ProcessedInvoice instance
        """
        invoice = ProcessedInvoice(
            stripe_id=stripe_id,
            invoice_type=invoice_type,
            provider=provider,
            customer_id=customer_id,
            customer_email=customer_email,
            customer_tax_id=customer_tax_id,
            amount=amount,
            currency=currency,
            invoice_date=invoice_date,
            status=ProcessingStatus.PENDING,
            attempts=0,
            extra_metadata=extra_metadata
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice
    
    @staticmethod
    def update_status(
        db: Session,
        invoice_id: int,
        status: ProcessingStatus,
        provider_invoice_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> ProcessedInvoice:
        """
        Update invoice processing status.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            status: New status
            provider_invoice_id: Optional provider invoice ID
            error_message: Optional error message
            
        Returns:
            Updated ProcessedInvoice instance
        """
        invoice = db.query(ProcessedInvoice).filter(
            ProcessedInvoice.id == invoice_id
        ).first()
        
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        invoice.status = status
        invoice.attempts += 1
        
        if provider_invoice_id:
            invoice.provider_invoice_id = provider_invoice_id
        
        if error_message:
            invoice.last_error = error_message
        
        if status == ProcessingStatus.COMPLETED:
            invoice.processed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(invoice)
        return invoice
    
    @staticmethod
    def get_pending_invoices(
        db: Session,
        provider: Optional[str] = None,
        limit: int = 100
    ) -> List[ProcessedInvoice]:
        """
        Get pending invoices for processing.
        
        Args:
            db: Database session
            provider: Optional provider filter
            limit: Maximum number of results
            
        Returns:
            List of pending invoices
        """
        query = db.query(ProcessedInvoice).filter(
            ProcessedInvoice.status == ProcessingStatus.PENDING
        )
        
        if provider:
            query = query.filter(ProcessedInvoice.provider == provider)
        
        return query.order_by(ProcessedInvoice.created_at).limit(limit).all()
    
    @staticmethod
    def get_failed_invoices(
        db: Session,
        provider: Optional[str] = None,
        max_attempts: int = 3
    ) -> List[ProcessedInvoice]:
        """
        Get failed invoices that can be retried.
        
        Args:
            db: Database session
            provider: Optional provider filter
            max_attempts: Maximum attempts filter
            
        Returns:
            List of failed invoices
        """
        query = db.query(ProcessedInvoice).filter(
            and_(
                ProcessedInvoice.status == ProcessingStatus.FAILED,
                ProcessedInvoice.attempts < max_attempts
            )
        )
        
        if provider:
            query = query.filter(ProcessedInvoice.provider == provider)
        
        return query.order_by(ProcessedInvoice.created_at).all()


class ProcessingHistoryCRUD:
    """CRUD operations for processing history."""
    
    @staticmethod
    def create_history(
        db: Session,
        invoice_id: int,
        stripe_id: str,
        provider: str,
        action: str,
        status: str,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        initiated_by: str = "system"
    ) -> ProcessingHistory:
        """
        Create a processing history record.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            stripe_id: Stripe ID
            provider: Provider name
            action: Action performed
            status: Result status
            request_data: Optional request data
            response_data: Optional response data
            error_message: Optional error message
            initiated_by: Who initiated the action
            
        Returns:
            Created ProcessingHistory instance
        """
        history = ProcessingHistory(
            invoice_id=invoice_id,
            stripe_id=stripe_id,
            provider=provider,
            action=action,
            status=status,
            request_data=request_data,
            response_data=response_data,
            error_message=error_message,
            initiated_by=initiated_by,
            started_at=datetime.utcnow()
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return history
    
    @staticmethod
    def complete_history(
        db: Session,
        history_id: int,
        status: str,
        response_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> ProcessingHistory:
        """
        Complete a processing history record.
        
        Args:
            db: Database session
            history_id: History record ID
            status: Final status
            response_data: Optional response data
            error_message: Optional error message
            
        Returns:
            Updated ProcessingHistory instance
        """
        history = db.query(ProcessingHistory).filter(
            ProcessingHistory.id == history_id
        ).first()
        
        if not history:
            raise ValueError(f"History record {history_id} not found")
        
        history.status = status
        history.completed_at = datetime.utcnow()
        history.duration_ms = int(
            (history.completed_at - history.started_at).total_seconds() * 1000
        )
        
        if response_data:
            history.response_data = response_data
        
        if error_message:
            history.error_message = error_message
        
        db.commit()
        db.refresh(history)
        return history
    
    @staticmethod
    def get_invoice_history(
        db: Session,
        invoice_id: int
    ) -> List[ProcessingHistory]:
        """
        Get processing history for an invoice.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            
        Returns:
            List of processing history records
        """
        return db.query(ProcessingHistory).filter(
            ProcessingHistory.invoice_id == invoice_id
        ).order_by(ProcessingHistory.started_at.desc()).all()


class AuditLogCRUD:
    """CRUD operations for audit logging."""
    
    @staticmethod
    def create_audit_log(
        db: Session,
        event_type: str,
        resource_type: str,
        action: str,
        resource_id: Optional[str] = None,
        description: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Create an audit log entry.
        
        Args:
            db: Database session
            event_type: Type of event
            resource_type: Type of resource
            action: Action performed
            resource_id: Optional resource ID
            description: Optional description
            changes: Optional before/after values
            extra_metadata: Optional additional metadata
            user_id: Optional user ID
            ip_address: Optional IP address
            user_agent: Optional user agent
            
        Returns:
            Created AuditLog instance
        """
        audit = AuditLog(
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            description=description,
            changes=changes,
            extra_metadata=extra_metadata,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    
    @staticmethod
    def get_audit_logs(
        db: Session,
        event_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Get audit logs with filters.
        
        Args:
            db: Database session
            event_type: Optional event type filter
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results
            
        Returns:
            List of audit log entries
        """
        query = db.query(AuditLog)
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        
        if resource_id:
            query = query.filter(AuditLog.resource_id == resource_id)
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()


class RetryQueueCRUD:
    """CRUD operations for retry queue."""
    
    @staticmethod
    def add_to_retry_queue(
        db: Session,
        invoice_id: int,
        stripe_id: str,
        provider: str,
        error_message: str,
        error_code: Optional[str] = None,
        retry_after_minutes: int = 30
    ) -> RetryQueue:
        """
        Add an invoice to the retry queue.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            stripe_id: Stripe ID
            provider: Provider name
            error_message: Error message
            error_code: Optional error code
            retry_after_minutes: Minutes to wait before retry
            
        Returns:
            Created RetryQueue instance
        """
        retry = RetryQueue(
            invoice_id=invoice_id,
            stripe_id=stripe_id,
            provider=provider,
            last_error=error_message,
            error_code=error_code,
            retry_after=datetime.utcnow() + timedelta(minutes=retry_after_minutes),
            retry_count=0,
            active=True
        )
        db.add(retry)
        db.commit()
        db.refresh(retry)
        return retry
    
    @staticmethod
    def get_ready_retries(
        db: Session,
        provider: Optional[str] = None
    ) -> List[RetryQueue]:
        """
        Get retries that are ready to be processed.
        
        Args:
            db: Database session
            provider: Optional provider filter
            
        Returns:
            List of retry queue entries
        """
        query = db.query(RetryQueue).filter(
            and_(
                RetryQueue.active == True,
                RetryQueue.completed == False,
                RetryQueue.retry_after <= datetime.utcnow(),
                RetryQueue.retry_count < RetryQueue.max_retries
            )
        )
        
        if provider:
            query = query.filter(RetryQueue.provider == provider)
        
        return query.order_by(RetryQueue.retry_after).all()
    
    @staticmethod
    def update_retry(
        db: Session,
        retry_id: int,
        success: bool,
        error_message: Optional[str] = None,
        retry_after_minutes: int = 60
    ) -> RetryQueue:
        """
        Update a retry queue entry.
        
        Args:
            db: Database session
            retry_id: Retry queue ID
            success: Whether the retry was successful
            error_message: Optional error message
            retry_after_minutes: Minutes to wait before next retry
            
        Returns:
            Updated RetryQueue instance
        """
        retry = db.query(RetryQueue).filter(
            RetryQueue.id == retry_id
        ).first()
        
        if not retry:
            raise ValueError(f"Retry queue entry {retry_id} not found")
        
        retry.retry_count += 1
        
        if success:
            retry.completed = True
            retry.active = False
        else:
            if error_message:
                retry.last_error = error_message
            
            if retry.retry_count >= retry.max_retries:
                retry.active = False
            else:
                retry.retry_after = datetime.utcnow() + timedelta(minutes=retry_after_minutes)
        
        db.commit()
        db.refresh(retry)
        return retry


class InvoiceDocumentCRUD:
    """CRUD operations for invoice documents."""
    
    @staticmethod
    def save_document(
        db: Session,
        invoice_id: int,
        stripe_id: str,
        provider: str,
        document_type: str,
        document_content: str,
        file_size: Optional[int] = None,
        checksum: Optional[str] = None,
        document_url: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> InvoiceDocument:
        """
        Save an invoice document.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            stripe_id: Stripe ID
            provider: Provider name
            document_type: Document type (xml, pdf, etc.)
            document_content: Document content (base64 for binary)
            file_size: Optional file size
            checksum: Optional file checksum
            document_url: Optional external URL
            expires_at: Optional expiration date
            
        Returns:
            Created InvoiceDocument instance
        """
        document = InvoiceDocument(
            invoice_id=invoice_id,
            stripe_id=stripe_id,
            provider=provider,
            document_type=document_type,
            document_content=document_content,
            file_size=file_size,
            checksum=checksum,
            document_url=document_url,
            expires_at=expires_at
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    
    @staticmethod
    def get_document(
        db: Session,
        invoice_id: int,
        document_type: str,
        provider: str
    ) -> Optional[InvoiceDocument]:
        """
        Get a specific document for an invoice.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            document_type: Document type
            provider: Provider name
            
        Returns:
            InvoiceDocument if found, None otherwise
        """
        return db.query(InvoiceDocument).filter(
            and_(
                InvoiceDocument.invoice_id == invoice_id,
                InvoiceDocument.document_type == document_type,
                InvoiceDocument.provider == provider
            )
        ).first()
    
    @staticmethod
    def get_invoice_documents(
        db: Session,
        invoice_id: int
    ) -> List[InvoiceDocument]:
        """
        Get all documents for an invoice.
        
        Args:
            db: Database session
            invoice_id: Invoice ID
            
        Returns:
            List of invoice documents
        """
        return db.query(InvoiceDocument).filter(
            InvoiceDocument.invoice_id == invoice_id
        ).order_by(InvoiceDocument.created_at.desc()).all()