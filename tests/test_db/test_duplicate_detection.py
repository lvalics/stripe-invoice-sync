"""Test duplicate invoice detection functionality."""
import pytest
from datetime import datetime
from app.db.database import get_db_context
from app.db.services import invoice_processing_service
from app.db.models import ProcessingStatus, InvoiceType
from app.core.provider_interface import InvoiceData, ProviderResponse, InvoiceStatus


def create_test_invoice_data(source_id: str) -> InvoiceData:
    """Create test invoice data."""
    return InvoiceData(
        # Source info
        source_type="stripe_charge",
        source_id=source_id,
        source_data={"test": True},
        
        # Invoice metadata
        invoice_number=f"TEST-{source_id[-6:]}",
        invoice_date=datetime.now(),
        currency="RON",
        
        # Customer information
        customer_id="cus_test123",
        customer_name="Test Customer",
        customer_email="test@example.com",
        customer_tax_id="RO12345678",
        customer_address={
            "line1": "Test Street 123",
            "city": "Bucharest",
            "country": "RO"
        },
        
        # Supplier information
        supplier_name="Test Supplier",
        supplier_tax_id="RO87654321",
        supplier_address={
            "line1": "Supplier Street 456",
            "city": "Bucharest", 
            "country": "RO"
        },
        
        # Invoice lines
        lines=[{
            "description": "Test Service",
            "quantity": 1,
            "unit_price": 100.0,
            "amount": 100.0,
            "tax_rate": 19.0
        }],
        
        # Totals
        subtotal=100.0,
        tax_amount=19.0,
        total=119.0,
        amount_paid=119.0,
        
        # Tax info
        tax_rate=19.0,
        
        # Additional metadata
        metadata={"test": True}
    )


class TestDuplicateDetection:
    """Test duplicate invoice detection."""
    
    def test_duplicate_detection_same_provider(self):
        """Test that duplicate invoices are detected for the same provider."""
        # Create test invoice
        source_id = f"ch_test_dup_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process first time
        invoice1, is_duplicate1 = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        assert invoice1 is not None
        assert is_duplicate1 is False
        assert invoice1.status == ProcessingStatus.PENDING
        
        # Process again - should detect duplicate
        invoice2, is_duplicate2 = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        assert invoice2 is not None
        assert is_duplicate2 is True
        assert invoice1.id == invoice2.id
        
    def test_different_providers_no_duplicate(self):
        """Test that same invoice can be processed by different providers."""
        # Create test invoice
        source_id = f"ch_test_multi_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process with ANAF
        invoice_anaf, is_dup_anaf = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        assert invoice_anaf is not None
        assert is_dup_anaf is False
        
        # Process with SmartBill - should NOT be duplicate
        invoice_smartbill, is_dup_smartbill = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="smartbill",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        assert invoice_smartbill is not None
        assert is_dup_smartbill is False
        assert invoice_anaf.id != invoice_smartbill.id
        
    def test_duplicate_with_completed_status(self):
        """Test duplicate detection returns completed status if already processed."""
        # Create test invoice
        source_id = f"ch_test_complete_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process and mark as completed
        invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Simulate successful processing
        success_response = ProviderResponse(
            success=True,
            provider="anaf",
            invoice_id="ANAF-123456",
            status=InvoiceStatus.SENT,
            message="Invoice processed successfully"
        )
        
        invoice_processing_service.update_invoice_status_with_history(
            invoice_id=invoice.id,
            provider_response=success_response,
            action="create_invoice"
        )
        
        # Try to process again
        invoice_dup, is_duplicate = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        assert is_duplicate is True
        assert invoice_dup.status == ProcessingStatus.COMPLETED
        assert invoice_dup.provider_invoice_id == "ANAF-123456"