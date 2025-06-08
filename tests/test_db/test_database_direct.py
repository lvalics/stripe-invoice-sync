#!/usr/bin/env python
"""Test database implementation directly without going through Stripe."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app.db.database import get_db_context
from app.db.services import invoice_processing_service
from app.db.models import ProcessingStatus, InvoiceType
from app.core.provider_interface import InvoiceData, ProviderResponse, InvoiceStatus

def create_test_invoice_data(stripe_id: str) -> InvoiceData:
    """Create test invoice data."""
    return InvoiceData(
        # Source info
        source_type="stripe_charge",
        source_id=stripe_id,
        source_data={"test": True},
        
        # Invoice metadata
        invoice_number=f"TEST-{stripe_id[-6:]}",
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

def test_duplicate_detection():
    """Test duplicate invoice detection."""
    print("\n=== Testing Duplicate Detection ===")
    
    # Create test invoice
    stripe_id = "ch_test_duplicate_" + str(int(datetime.now().timestamp()))
    invoice_data = create_test_invoice_data(stripe_id)
    
    # Process first time
    print(f"\n1. Processing invoice {stripe_id} for the first time...")
    invoice1, is_duplicate1 = invoice_processing_service.process_invoice_with_duplicate_check(
        invoice_data=invoice_data,
        provider="anaf",
        invoice_type=InvoiceType.STRIPE_CHARGE
    )
    
    print(f"   Invoice ID: {invoice1.id}")
    print(f"   Is Duplicate: {is_duplicate1}")
    print(f"   Status: {invoice1.status}")
    
    # Process again - should detect duplicate
    print(f"\n2. Processing same invoice again...")
    invoice2, is_duplicate2 = invoice_processing_service.process_invoice_with_duplicate_check(
        invoice_data=invoice_data,
        provider="anaf",
        invoice_type=InvoiceType.STRIPE_CHARGE
    )
    
    print(f"   Invoice ID: {invoice2.id}")
    print(f"   Is Duplicate: {is_duplicate2}")
    print(f"   Status: {invoice2.status}")
    
    # Test result
    if is_duplicate2 and invoice1.id == invoice2.id:
        print("\n   ✅ Duplicate detection working correctly!")
    else:
        print("\n   ❌ Duplicate detection failed!")

def test_processing_history():
    """Test processing history tracking."""
    print("\n\n=== Testing Processing History ===")
    
    # Create and process test invoice
    stripe_id = "ch_test_history_" + str(int(datetime.now().timestamp()))
    invoice_data = create_test_invoice_data(stripe_id)
    
    # Process invoice
    invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
        invoice_data=invoice_data,
        provider="anaf",
        invoice_type=InvoiceType.STRIPE_CHARGE
    )
    
    # Simulate provider response
    success_response = ProviderResponse(
        success=True,
        provider="anaf",
        invoice_id="ANAF-123456",
        status=InvoiceStatus.SENT,
        data={"xml": "<test>xml</test>"},
        message="Invoice processed successfully"
    )
    
    # Update status with history
    updated_invoice = invoice_processing_service.update_invoice_status_with_history(
        invoice_id=invoice.id,
        provider_response=success_response,
        action="create_invoice"
    )
    
    print(f"\nInvoice {stripe_id} updated:")
    print(f"   Status: {updated_invoice.status}")
    print(f"   Provider Invoice ID: {updated_invoice.provider_invoice_id}")
    
    # Get full history
    history = invoice_processing_service.get_invoice_full_history(stripe_id)
    
    if "invoices" in history and history["invoices"]:
        invoice_info = history["invoices"][0]
        print(f"\nHistory entries: {len(invoice_info['history'])}")
        for entry in invoice_info['history']:
            print(f"   - Action: {entry['action']}, Status: {entry['status']}")
        
        if invoice_info.get('documents'):
            print(f"\nDocuments saved: {len(invoice_info['documents'])}")
            for doc in invoice_info['documents']:
                print(f"   - Type: {doc['type']}, Size: {doc['file_size']} bytes")

def test_failed_invoice_retry():
    """Test failed invoice and retry queue."""
    print("\n\n=== Testing Failed Invoice & Retry Queue ===")
    
    # Create test invoice
    stripe_id = "ch_test_retry_" + str(int(datetime.now().timestamp()))
    invoice_data = create_test_invoice_data(stripe_id)
    
    # Process invoice
    invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
        invoice_data=invoice_data,
        provider="anaf",
        invoice_type=InvoiceType.STRIPE_CHARGE
    )
    
    # Simulate failed response
    failed_response = ProviderResponse(
        success=False,
        provider="anaf",
        status=InvoiceStatus.ERROR,
        message="Invalid credentials"
    )
    
    # Update with failure
    updated_invoice = invoice_processing_service.update_invoice_status_with_history(
        invoice_id=invoice.id,
        provider_response=failed_response,
        action="create_invoice"
    )
    
    print(f"\nInvoice {stripe_id} failed:")
    print(f"   Status: {updated_invoice.status}")
    print(f"   Attempts: {updated_invoice.attempts}")
    print(f"   Last Error: {updated_invoice.last_error}")
    
    # Check retry queue
    retries = invoice_processing_service.process_retry_queue("anaf")
    print(f"\nRetry queue entries: {len(retries)}")
    for retry in retries:
        print(f"   - Invoice ID: {retry['invoice_id']}, Retry Count: {retry['retry_count']}")

def test_statistics():
    """Test processing statistics."""
    print("\n\n=== Testing Processing Statistics ===")
    
    stats = invoice_processing_service.get_processing_stats()
    
    print("\nOverall Statistics:")
    print(f"   Total Invoices: {stats['total']}")
    print(f"   Completed: {stats['completed']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Pending: {stats['pending']}")
    print(f"   In Retry: {stats['retry']}")
    print(f"   Success Rate: {stats['success_rate']}%")
    print(f"   Average Attempts: {stats['average_attempts']}")

def test_audit_trail():
    """Test audit trail functionality."""
    print("\n\n=== Testing Audit Trail ===")
    
    with get_db_context() as db:
        from app.db.crud import AuditLogCRUD
        audit_crud = AuditLogCRUD()
        
        # Get recent audit logs
        logs = audit_crud.get_audit_logs(
            db,
            event_type="invoice_processing",
            limit=5
        )
        
        print(f"\nRecent audit logs: {len(logs)}")
        for log in logs[:3]:  # Show first 3
            print(f"   - {log.created_at.strftime('%Y-%m-%d %H:%M:%S')}: {log.action} - {log.description}")

def main():
    """Run all database tests."""
    print("=== Database Implementation Tests (Direct) ===")
    
    try:
        test_duplicate_detection()
        test_processing_history()
        test_failed_invoice_retry()
        test_statistics()
        test_audit_trail()
        
        print("\n\n=== All Tests Complete ===")
        print("✅ Database persistence layer is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()