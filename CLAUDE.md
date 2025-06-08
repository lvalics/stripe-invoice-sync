# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Stripe Invoice Sync is a modular Python API system that syncs Stripe invoices and charges with Romanian invoice providers (ANAF e-Factura, SmartBill, etc.). It provides a plugin-based architecture where new invoice providers can be easily added without modifying core code.

The system can fetch both Stripe invoices (when generated) and charges (direct payments) and process them through any configured provider via REST API or automation scripts.

## Development Commands

From the `stripe-invoice-sync` directory:

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run API server
uvicorn app.main:app --reload  # Development with auto-reload
python -m app.main              # Production

# Run tests
pytest                          # Run all tests
pytest tests/test_providers.py  # Run specific test file
pytest -v                       # Verbose output
pytest --cov=app               # With coverage report

# Code quality
black app/                      # Format code
flake8 app/                    # Lint code

# Process invoices via CLI
python scripts/process_invoices.py --provider anaf --type invoices --days 7
python scripts/sync_customers.py --mappings customers.csv --validate
```

## Architecture

### Plugin-Based Provider System

The system uses a provider interface pattern where each invoice provider (ANAF, SmartBill, etc.) implements `InvoiceProviderInterface`:

```
app/
├── core/
│   ├── provider_interface.py  # Base interface all providers must implement
│   └── provider_factory.py    # Factory for creating provider instances
├── providers/
│   ├── anaf_provider.py      # ANAF e-Factura implementation
│   └── smartbill_provider.py # SmartBill implementation
└── services/
    └── stripe_service.py      # Handles both invoices and charges from Stripe
```

### Key Architectural Decisions

1. **Dual Stripe Data Sources**: The `StripeService` can fetch both:
   - Stripe Invoices (via `fetch_invoices()`) - when invoices are generated
   - Stripe Charges (via `fetch_charges()`) - for direct payments without invoices

2. **Standardized Data Format**: All Stripe data is converted to `InvoiceData` model before processing, allowing providers to work with consistent data structure.

3. **Provider Independence**: Each provider is self-contained with its own authentication, data transformation, and API communication logic.

4. **Async Architecture**: All provider methods are async, enabling efficient parallel processing and non-blocking I/O.

### Provider Implementation

When implementing a new provider:

1. Inherit from `InvoiceProviderInterface`
2. Implement required methods:
   - `validate_credentials()` - Check authentication
   - `create_invoice()` - Submit invoice to provider
   - `get_invoice_status()` - Check processing status
   - `download_invoice()` - Retrieve processed invoice
   - `get_company_info()` - Optional company lookup

3. Register in `provider_factory.py`
4. Add configuration in settings

### Data Flow

1. **Stripe → StandardFormat**: Raw Stripe data is converted to `InvoiceData`
2. **StandardFormat → Provider**: Each provider transforms to its specific format
3. **Provider → External API**: Provider handles authentication and API calls
4. **Response → StandardResponse**: Results returned in `ProviderResponse` format

## Key Implementation Details

### Environment Configuration

The system uses Pydantic Settings for configuration management. Key settings in `app/config/settings.py`:
- Provider credentials are loaded from environment variables
- Each provider can be enabled/disabled independently
- Default values for invoicing (series, tax rate, currency)

### XML Generation for ANAF

The `ANAFXMLGenerator` in `app/utils/xml_generator.py` creates UBL 2.1 compliant invoices:
- Proper namespace handling with lxml
- CIUS-RO-1.3.0 specification compliance
- Automatic tax calculations and breakdowns

### Rate Limiting and Error Handling

- Built-in rate limiting per provider (configurable)
- Comprehensive error handling with detailed error messages
- Retry logic for transient failures
- Validation at multiple levels (data, provider-specific, API)

### Automation Scripts

The `scripts/` directory contains standalone automation tools:
- `process_invoices.py` - Batch process invoices/charges with date filtering
- `sync_customers.py` - Manage customer tax ID mappings

These scripts use the API internally but provide CLI interfaces for cron jobs and automation.

## API Documentation

### Postman Collection

A Postman collection is maintained at `postman_collection.json` for easy API testing and documentation. 

**To use the collection:**
1. Import `postman_collection.json` into Postman
2. Set the `baseUrl` variable (default: `http://localhost:8000`)
3. Set the `provider` variable (default: `anaf`)

**When adding new endpoints:**
1. Add the endpoint to the appropriate folder in the collection
2. Include all required/optional parameters with descriptions
3. Add example request bodies for POST endpoints
4. Update the collection version if making significant changes

**To regenerate the collection from code:**
```bash
# The collection structure mirrors the API organization:
# - Root & Health: System status endpoints
# - Stripe API: Stripe data fetching endpoints
# - Invoice Processing: Core invoice processing endpoints
# - Provider Management: Provider configuration/validation
# - ANAF Specific: ANAF-specific functionality
# - Documentation: Auto-generated API docs
```

### Interactive Documentation

The API provides auto-generated interactive documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

These are automatically updated when endpoints are added/modified.