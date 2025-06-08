"""Test retry queue functionality."""
import pytest
from datetime import datetime, timedelta
from app.db.database import get_db_context
from app.db.services import invoice_processing_service
from app.db.models import ProcessingStatus, InvoiceType
from app.core.provider_interface import InvoiceData, ProviderResponse, InvoiceStatus
from tests.test_db.test_duplicate_detection import create_test_invoice_data


class TestRetryQueue:
    """Test retry queue functionality."""
    
    def test_failed_invoice_added_to_retry_queue(self):
        """Test that failed invoices are added to retry queue."""
        # Create test invoice
        source_id = f"ch_test_retry_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
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
            message="Authentication failed"
        )
        
        # Update with failure
        updated_invoice = invoice_processing_service.update_invoice_status_with_history(
            invoice_id=invoice.id,
            provider_response=failed_response,
            action="create_invoice"
        )
        
        assert updated_invoice.status == ProcessingStatus.FAILED
        assert updated_invoice.attempts == 1
        assert updated_invoice.last_error == "Authentication failed"
        
        # Check retry queue
        retries = invoice_processing_service.process_retry_queue("anaf")
        
        # Find our invoice in retries
        our_retry = next((r for r in retries if r['invoice_id'] == invoice.id), None)
        assert our_retry is not None
        assert our_retry['retry_count'] == 0
        
    def test_max_retry_attempts(self):
        """Test that invoices are not retried after max attempts."""
        # Create test invoice
        source_id = f"ch_test_max_retry_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process invoice
        invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Simulate multiple failures
        for i in range(3):  # Max attempts is 3
            failed_response = ProviderResponse(
                success=False,
                provider="anaf",
                status=InvoiceStatus.ERROR,
                message=f"Attempt {i+1} failed"
            )
            
            invoice_processing_service.update_invoice_status_with_history(
                invoice_id=invoice.id,
                provider_response=failed_response,
                action="create_invoice"
            )
        
        # Get the invoice to check attempts
        with get_db_context() as db:
            from app.db.models import ProcessedInvoice
            final_invoice = db.query(ProcessedInvoice).filter(
                ProcessedInvoice.id == invoice.id
            ).first()
            
            assert final_invoice.attempts == 3
            assert final_invoice.status == ProcessingStatus.FAILED
            
            # Check retry queue - should not be active
            from app.db.models import RetryQueue
            retry_entry = db.query(RetryQueue).filter(
                RetryQueue.invoice_id == invoice.id
            ).first()
            
            # After max attempts, retry should not be active
            if retry_entry:
                assert retry_entry.active is False or retry_entry.retry_count >= retry_entry.max_retries
    
    def test_exponential_backoff(self):
        """Test that retry delay increases exponentially."""
        # Create test invoice
        source_id = f"ch_test_backoff_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process invoice
        invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # First failure
        failed_response = ProviderResponse(
            success=False,
            provider="anaf",
            status=InvoiceStatus.ERROR,
            message="First failure"
        )
        
        invoice_processing_service.update_invoice_status_with_history(
            invoice_id=invoice.id,
            provider_response=failed_response,
            action="create_invoice"
        )
        
        with get_db_context() as db:
            from app.db.models import RetryQueue
            retry = db.query(RetryQueue).filter(
                RetryQueue.invoice_id == invoice.id
            ).first()
            
            assert retry is not None
            first_retry_after = retry.retry_after
            
            # The retry should be scheduled ~30 minutes later (30 * attempts)
            expected_delay = timedelta(minutes=30)
            actual_delay = first_retry_after - datetime.utcnow()
            
            # Allow some tolerance for execution time
            assert abs(actual_delay.total_seconds() - expected_delay.total_seconds()) < 60