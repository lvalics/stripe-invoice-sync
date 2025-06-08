"""SQLAlchemy models for database persistence."""
from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean, Text, JSON, Index, UniqueConstraint
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum as PyEnum

from app.db.database import Base


class ProcessingStatus(str, PyEnum):
    """Invoice processing status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class InvoiceType(str, PyEnum):
    """Type of invoice source."""
    STRIPE_INVOICE = "stripe_invoice"
    STRIPE_CHARGE = "stripe_charge"


class ProcessedInvoice(Base):
    """Track processed invoices to prevent duplicates."""
    __tablename__ = "processed_invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    stripe_id = Column(String(255), nullable=False, index=True)
    invoice_type = Column(String(50), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_invoice_id = Column(String(255))
    status = Column(String(50), nullable=False, default=ProcessingStatus.PENDING)
    
    # Invoice data
    customer_id = Column(String(255))
    customer_email = Column(String(255))
    customer_tax_id = Column(String(100))
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)
    invoice_date = Column(DateTime, nullable=False)
    
    # Processing metadata
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    processed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Additional data
    extra_metadata = Column(JSON)
    
    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('stripe_id', 'provider', name='uix_stripe_provider'),
        Index('ix_customer_id', 'customer_id'),
        Index('ix_status_created', 'status', 'created_at'),
        Index('ix_provider_status', 'provider', 'status'),
    )


class ProcessingHistory(Base):
    """Track all processing attempts for audit trail."""
    __tablename__ = "processing_history"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    stripe_id = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)  # create, status_check, download, etc.
    status = Column(String(50), nullable=False)
    
    # Request/Response data
    request_data = Column(JSON)
    response_data = Column(JSON)
    error_message = Column(Text)
    
    # Timing
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)
    
    # User/System tracking
    initiated_by = Column(String(100), default="system")
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    
    __table_args__ = (
        Index('ix_invoice_created', 'invoice_id', 'started_at'),
        Index('ix_stripe_id_history', 'stripe_id'),
    )


class AuditLog(Base):
    """Audit trail for all system operations."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255))
    action = Column(String(50), nullable=False)
    
    # Event details
    description = Column(Text)
    changes = Column(JSON)  # before/after values for updates
    extra_metadata = Column(JSON)
    
    # User/System info
    user_id = Column(String(100))
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    
    # Timestamp
    created_at = Column(DateTime, default=func.now(), index=True)
    
    __table_args__ = (
        Index('ix_resource', 'resource_type', 'resource_id'),
        Index('ix_event_created', 'event_type', 'created_at'),
    )


class RetryQueue(Base):
    """Queue for failed invoices that need retry."""
    __tablename__ = "retry_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    stripe_id = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    
    # Retry configuration
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    retry_after = Column(DateTime, nullable=False, index=True)
    
    # Error tracking
    last_error = Column(Text)
    error_code = Column(String(100))
    
    # Status
    active = Column(Boolean, default=True, index=True)
    completed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_active_retry', 'active', 'retry_after'),
        Index('ix_invoice_active', 'invoice_id', 'active'),
    )


class InvoiceDocument(Base):
    """Store generated invoice documents and XML."""
    __tablename__ = "invoice_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    stripe_id = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False)
    
    # Document data
    document_type = Column(String(50), nullable=False)  # xml, pdf, etc.
    document_content = Column(Text)  # Base64 encoded for binary
    document_url = Column(String(500))  # External URL if stored elsewhere
    
    # Metadata
    file_size = Column(Integer)
    checksum = Column(String(64))  # SHA256 hash
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    
    __table_args__ = (
        Index('ix_invoice_type', 'invoice_id', 'document_type'),
        UniqueConstraint('invoice_id', 'document_type', 'provider', name='uix_invoice_doc_provider'),
    )


class ProviderConfig(Base):
    """Store provider configurations (for future multitenancy)."""
    __tablename__ = "provider_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, unique=True)
    active = Column(Boolean, default=True)
    
    # Configuration
    config_data = Column(JSON, nullable=False)  # Encrypted in production
    
    # Rate limiting
    rate_limit = Column(Integer, default=100)
    rate_window = Column(Integer, default=3600)  # seconds
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_provider_active', 'provider', 'active'),
    )