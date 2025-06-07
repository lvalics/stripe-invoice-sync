# Stripe Invoice Sync

A modular Python API for syncing Stripe invoices and charges with multiple Romanian invoice providers (ANAF e-Factura, SmartBill, etc.).

## Features

- **Multi-Provider Support**: Pluggable architecture supporting ANAF, SmartBill, and custom providers
- **Dual Stripe Data Sources**: Process both Stripe invoices and charges/orders
- **Flexible Processing**: REST API, CLI tools, and automation scripts
- **Company Validation**: Romanian CUI validation and ANAF company lookup
- **Batch Processing**: Efficient bulk invoice processing with rate limiting
- **No Frontend Required**: Fully functional via API and scripts

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Stripe      │────▶│   Sync Engine   │────▶│    Providers    │
│  (Invoices &    │     │   (FastAPI)     │     │  (ANAF, etc.)   │
│    Charges)     │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Automation      │
                        │   Scripts       │
                        └─────────────────┘
```

## Installation

1. Clone the repository:
```bash
cd stripe-invoice-sync
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

### Required Environment Variables

- `STRIPE_API_KEY`: Your Stripe secret key
- `COMPANY_NAME`: Your company name
- `COMPANY_CUI`: Your company tax ID (CUI)
- `COMPANY_ADDRESS_*`: Your company address details

### Provider Configuration

#### ANAF e-Factura
- `ANAF_CLIENT_ID`: OAuth2 client ID
- `ANAF_CLIENT_SECRET`: OAuth2 client secret
- `ANAF_ENABLED`: Enable/disable provider

#### SmartBill
- `SMARTBILL_USERNAME`: Account email
- `SMARTBILL_TOKEN`: API token
- `SMARTBILL_ENABLED`: Enable/disable provider

## Usage

### 1. Start the API Server

```bash
python -m app.main
# or
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 2. API Endpoints

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Fetch Stripe Invoices
```bash
curl "http://localhost:8000/api/stripe/invoices?start_date=2024-01-01&end_date=2024-01-31"
```

#### Fetch Stripe Charges
```bash
curl "http://localhost:8000/api/stripe/charges?start_date=2024-01-01&end_date=2024-01-31"
```

#### Process Single Invoice
```bash
curl -X POST http://localhost:8000/api/invoices/process \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "stripe_invoice",
    "source_id": "in_1234567890",
    "provider": "anaf",
    "customer_tax_id": "RO12345678"
  }'
```

#### Batch Process
```bash
curl -X POST http://localhost:8000/api/invoices/process/batch \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anaf",
    "invoices": [
      {"source_type": "stripe_invoice", "source_id": "in_123"},
      {"source_type": "stripe_charge", "source_id": "ch_456"}
    ]
  }'
```

#### Company Lookup
```bash
curl http://localhost:8000/api/anaf/company/12345678
```

### 3. Automation Scripts

#### Process Recent Invoices
```bash
# Process last 7 days of invoices through ANAF
python scripts/process_invoices.py --provider anaf --type invoices --days 7

# Process specific date range
python scripts/process_invoices.py \
  --provider smartbill \
  --type both \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --output results.json

# Dry run (fetch but don't process)
python scripts/process_invoices.py --provider anaf --dry-run
```

#### Sync Customer Tax IDs
```bash
# Create a CSV file with email,cui mappings
echo "email,cui" > customers.csv
echo "client@example.com,RO12345678" >> customers.csv

# Sync and validate
python scripts/sync_customers.py \
  --mappings customers.csv \
  --validate \
  --output validated_customers.json
```

### 4. Scheduled Processing (Cron)

Add to crontab for daily processing:
```bash
# Process yesterday's invoices daily at 2 AM
0 2 * * * /path/to/venv/bin/python /path/to/scripts/process_invoices.py --provider anaf --days 1
```

## Adding New Providers

1. Create provider class in `app/providers/`:
```python
from app.core.provider_interface import InvoiceProviderInterface

class MyProvider(InvoiceProviderInterface):
    async def create_invoice(self, invoice_data):
        # Implementation
        pass
```

2. Register in `app/core/provider_factory.py`:
```python
ProviderFactory.register_provider("myprovider", MyProvider)
```

3. Add configuration in `.env`:
```
MYPROVIDER_ENABLED=true
MYPROVIDER_API_KEY=xxx
```

## API Documentation

When running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## Error Handling

The system provides detailed error responses:
```json
{
  "source_id": "in_123",
  "provider": "anaf",
  "status": "error",
  "errors": ["Customer tax ID is required"],
  "timestamp": "2024-01-15T10:30:00"
}
```

## Monitoring

- Check `/health` endpoint for provider status
- Log files contain detailed processing information
- Results can be saved to JSON/CSV for analysis

## Security Notes

- Store API keys securely (use environment variables)
- Enable HTTPS in production
- Implement rate limiting for public endpoints
- Regularly rotate API credentials

## License

MIT License - see LICENSE file for details