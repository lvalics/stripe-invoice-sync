"""
Base interface for invoice providers (ANAF, SmartBill, etc.)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class InvoiceStatus(str, Enum):
    """Standard invoice statuses across providers"""
    DRAFT = "draft"
    PENDING = "pending"
    SENT = "sent"
    PAID = "paid"
    CANCELLED = "cancelled"
    ERROR = "error"


class ProviderConfig(BaseModel):
    """Base configuration for providers"""
    name: str
    enabled: bool = True
    api_endpoint: Optional[str] = None
    auth_type: str = "api_key"  # api_key, oauth2, basic
    credentials: Dict[str, Any] = {}
    options: Dict[str, Any] = {}


class InvoiceData(BaseModel):
    """Standardized invoice data structure"""
    # Invoice metadata
    provider_invoice_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: datetime
    due_date: Optional[datetime] = None
    currency: str = "RON"
    
    # Source information
    source_type: str  # "stripe_invoice" or "stripe_charge"
    source_id: str
    source_data: Dict[str, Any]
    
    # Customer information
    customer_id: str
    customer_name: str
    customer_email: str
    customer_tax_id: Optional[str] = None
    customer_address: Optional[Dict[str, str]] = None
    customer_country: str = "RO"
    
    # Supplier information (your company)
    supplier_name: str
    supplier_tax_id: str
    supplier_address: Dict[str, str]
    supplier_registration: Optional[str] = None
    
    # Invoice lines
    lines: List[Dict[str, Any]]
    
    # Totals
    subtotal: float
    tax_amount: float
    total: float
    amount_paid: float
    
    # Tax information
    tax_rate: float = 19.0
    tax_breakdown: List[Dict[str, Any]] = []
    
    # Additional metadata
    metadata: Dict[str, Any] = {}
    

class ProviderResponse(BaseModel):
    """Standardized response from providers"""
    success: bool
    provider: str
    invoice_id: Optional[str] = None
    external_id: Optional[str] = None  # Provider's invoice ID
    status: InvoiceStatus
    message: Optional[str] = None
    errors: List[str] = []
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.now()


class InvoiceProviderInterface(ABC):
    """Abstract base class for invoice providers"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        
    @abstractmethod
    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate provider credentials"""
        pass
    
    @abstractmethod
    async def create_invoice(self, invoice_data: InvoiceData) -> ProviderResponse:
        """Create invoice in the provider's system"""
        pass
    
    @abstractmethod
    async def get_invoice_status(self, invoice_id: str) -> ProviderResponse:
        """Get status of a previously created invoice"""
        pass
    
    @abstractmethod
    async def download_invoice(self, invoice_id: str, format: str = "pdf") -> Optional[bytes]:
        """Download invoice in specified format"""
        pass
    
    @abstractmethod
    async def cancel_invoice(self, invoice_id: str) -> ProviderResponse:
        """Cancel an invoice"""
        pass
    
    @abstractmethod
    async def get_company_info(self, tax_id: str) -> Optional[Dict[str, Any]]:
        """Get company information by tax ID (if supported)"""
        pass
    
    async def supports_batch_processing(self) -> bool:
        """Check if provider supports batch invoice creation"""
        return False
    
    async def create_batch_invoices(self, invoices: List[InvoiceData]) -> List[ProviderResponse]:
        """Create multiple invoices (if supported)"""
        if not await self.supports_batch_processing():
            # Fall back to sequential processing
            responses = []
            for invoice in invoices:
                response = await self.create_invoice(invoice)
                responses.append(response)
            return responses
        raise NotImplementedError("Batch processing not implemented")
    
    def transform_to_provider_format(self, invoice_data: InvoiceData) -> Dict[str, Any]:
        """Transform standardized invoice data to provider-specific format"""
        raise NotImplementedError("Each provider must implement data transformation")
    
    def validate_invoice_data(self, invoice_data: InvoiceData) -> List[str]:
        """Validate invoice data for provider requirements"""
        errors = []
        
        # Common validations
        if not invoice_data.customer_name:
            errors.append("Customer name is required")
        
        if self.config.options.get("require_tax_id", True) and not invoice_data.customer_tax_id:
            errors.append("Customer tax ID is required")
            
        if not invoice_data.lines:
            errors.append("Invoice must have at least one line item")
            
        return errors