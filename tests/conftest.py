"""Pytest configuration and fixtures."""
import pytest
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///test_stripe_invoice_sync.db"


@pytest.fixture(scope="session")
def setup_database():
    """Set up test database."""
    from app.db.database import init_db, engine, Base
    
    # Create all tables
    init_db()
    
    yield
    
    # Clean up after all tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_database(setup_database):
    """Clean database before each test."""
    from app.db.database import engine
    from sqlalchemy import text
    
    # Get all table names
    with engine.connect() as conn:
        # Clear all tables except alembic_version
        tables = ["processed_invoices", "processing_history", "audit_logs", 
                 "retry_queue", "invoice_documents", "provider_configs"]
        
        for table in tables:
            try:
                conn.execute(text(f"DELETE FROM {table}"))
                conn.commit()
            except Exception:
                pass  # Table might not exist


@pytest.fixture
def test_invoice_data():
    """Create test invoice data."""
    from datetime import datetime
    from app.core.provider_interface import InvoiceData
    
    def _create_invoice(source_id: str = None):
        if not source_id:
            source_id = f"ch_test_{int(datetime.now().timestamp())}"
            
        return InvoiceData(
            source_type="stripe_charge",
            source_id=source_id,
            source_data={"test": True},
            invoice_number=f"TEST-{source_id[-6:]}",
            invoice_date=datetime.now(),
            currency="RON",
            customer_id="cus_test123",
            customer_name="Test Customer",
            customer_email="test@example.com",
            customer_tax_id="RO12345678",
            customer_address={
                "line1": "Test Street 123",
                "city": "Bucharest",
                "country": "RO"
            },
            supplier_name="Test Supplier",
            supplier_tax_id="RO87654321",
            supplier_address={
                "line1": "Supplier Street 456",
                "city": "Bucharest", 
                "country": "RO"
            },
            lines=[{
                "description": "Test Service",
                "quantity": 1,
                "unit_price": 100.0,
                "amount": 100.0,
                "tax_rate": 19.0
            }],
            subtotal=100.0,
            tax_amount=19.0,
            total=119.0,
            amount_paid=119.0,
            tax_rate=19.0,
            metadata={"test": True}
        )
    
    return _create_invoice