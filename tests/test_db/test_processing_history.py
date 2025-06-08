"""Test processing history and audit trail functionality."""
import pytest
from datetime import datetime
from app.db.database import get_db_context
from app.db.services import invoice_processing_service
from app.db.models import ProcessingStatus, InvoiceType
from app.core.provider_interface import InvoiceData, ProviderResponse, InvoiceStatus
from tests.test_db.test_duplicate_detection import create_test_invoice_data


class TestProcessingHistory:
    """Test processing history tracking."""
    
    def test_history_creation_on_invoice_create(self):
        """Test that history entry is created when invoice is created."""
        # Create test invoice
        source_id = f"ch_test_history_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process invoice
        invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Get history
        history = invoice_processing_service.get_invoice_full_history(source_id)
        
        assert "invoices" in history
        assert len(history["invoices"]) == 1
        
        invoice_history = history["invoices"][0]
        assert len(invoice_history["history"]) >= 1
        
        # Check initial creation entry
        creation_entry = next(
            (h for h in invoice_history["history"] if h["action"] == "created"),
            None
        )
        assert creation_entry is not None
        assert creation_entry["status"] == "success"
        
    def test_history_tracking_for_processing(self):
        """Test that all processing steps are tracked in history."""
        # Create test invoice
        source_id = f"ch_test_process_history_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process invoice
        invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Simulate successful processing
        success_response = ProviderResponse(
            success=True,
            provider="anaf",
            invoice_id="ANAF-789",
            status=InvoiceStatus.SENT,
            data={"xml": "<invoice>test</invoice>"},
            message="Invoice sent successfully"
        )
        
        invoice_processing_service.update_invoice_status_with_history(
            invoice_id=invoice.id,
            provider_response=success_response,
            action="create_invoice"
        )
        
        # Get updated history
        history = invoice_processing_service.get_invoice_full_history(source_id)
        invoice_history = history["invoices"][0]
        
        # Should have at least 2 entries: created and create_invoice
        assert len(invoice_history["history"]) >= 2
        
        # Check processing entry
        processing_entry = next(
            (h for h in invoice_history["history"] if h["action"] == "create_invoice"),
            None
        )
        assert processing_entry is not None
        assert processing_entry["status"] == "success"
        assert processing_entry["duration_ms"] is not None
        
        # Check document was saved
        assert len(invoice_history["documents"]) >= 1
        doc = invoice_history["documents"][0]
        assert doc["type"] == "xml"
        assert doc["checksum"] is not None
        
    def test_failed_processing_history(self):
        """Test that failed attempts are properly tracked."""
        # Create test invoice
        source_id = f"ch_test_fail_history_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process invoice
        invoice, _ = invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Simulate failed processing
        failed_response = ProviderResponse(
            success=False,
            provider="anaf",
            status=InvoiceStatus.ERROR,
            message="Invalid authentication token"
        )
        
        invoice_processing_service.update_invoice_status_with_history(
            invoice_id=invoice.id,
            provider_response=failed_response,
            action="create_invoice"
        )
        
        # Get history
        history = invoice_processing_service.get_invoice_full_history(source_id)
        invoice_history = history["invoices"][0]
        
        # Check failed entry
        failed_entry = next(
            (h for h in invoice_history["history"] 
             if h["action"] == "create_invoice" and h["status"] == "failed"),
            None
        )
        assert failed_entry is not None
        assert failed_entry["error_message"] == "Invalid authentication token"
        
        # Check retry status
        assert invoice_history["retry_status"] is not None
        assert invoice_history["retry_status"]["active"] is True
        assert invoice_history["retry_status"]["last_error"] == "Invalid authentication token"


class TestAuditLog:
    """Test audit log functionality."""
    
    def test_audit_log_creation(self):
        """Test that audit logs are created for key events."""
        # Create test invoice
        source_id = f"ch_test_audit_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process invoice
        invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Check audit logs
        with get_db_context() as db:
            from app.db.crud import AuditLogCRUD
            audit_crud = AuditLogCRUD()
            
            logs = audit_crud.get_audit_logs(
                db,
                event_type="invoice_processing",
                resource_id=source_id,
                limit=10
            )
            
            assert len(logs) >= 1
            
            # Check creation log
            creation_log = next(
                (log for log in logs if log.action == "created"),
                None
            )
            assert creation_log is not None
            assert creation_log.resource_type == "invoice"
            assert "anaf" in creation_log.description.lower()
    
    def test_duplicate_detection_audit(self):
        """Test that duplicate detection is logged in audit trail."""
        # Create test invoice
        source_id = f"ch_test_dup_audit_{int(datetime.now().timestamp())}"
        invoice_data = create_test_invoice_data(source_id)
        
        # Process twice
        invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        invoice_processing_service.process_invoice_with_duplicate_check(
            invoice_data=invoice_data,
            provider="anaf",
            invoice_type=InvoiceType.STRIPE_CHARGE
        )
        
        # Check audit logs
        with get_db_context() as db:
            from app.db.crud import AuditLogCRUD
            audit_crud = AuditLogCRUD()
            
            logs = audit_crud.get_audit_logs(
                db,
                event_type="invoice_processing",
                resource_id=source_id,
                limit=10
            )
            
            # Should have both creation and duplicate detection
            duplicate_log = next(
                (log for log in logs if log.action == "duplicate_detected"),
                None
            )
            assert duplicate_log is not None
            assert "duplicate" in duplicate_log.description.lower()