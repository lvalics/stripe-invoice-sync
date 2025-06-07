# Stripe Invoice Sync - Complete Usage Guide

This guide provides detailed instructions on how to use the Stripe Invoice Sync system for processing Stripe invoices and charges through Romanian invoice providers.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [API Usage](#api-usage)
4. [Command Line Tools](#command-line-tools)
5. [Automation & Scheduling](#automation--scheduling)
6. [Common Workflows](#common-workflows)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Initial Setup

```bash
# Clone and enter the directory
cd stripe-invoice-sync

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start the API Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload

# Production mode
python -m app.main
```

The API will be available at `http://localhost:8000`

### 3. Quick Test

```bash
# Check system health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

## Configuration

### Essential Environment Variables

```bash
# Stripe Configuration (Required)
STRIPE_API_KEY=sk_live_your_stripe_secret_key

# Your Company Information (Required)
COMPANY_NAME="Your Company SRL"
COMPANY_CUI=RO12345678
COMPANY_ADDRESS_STREET="Str. Example nr. 1"
COMPANY_ADDRESS_CITY="București"
COMPANY_ADDRESS_POSTAL="010101"
COMPANY_REGISTRATION=J40/1234/2020  # Optional

# Invoice Defaults
DEFAULT_INVOICE_SERIES=FACT
DEFAULT_TAX_RATE=19.0
DEFAULT_CURRENCY=RON
```

### Provider-Specific Configuration

#### ANAF e-Factura
```bash
ANAF_ENABLED=true
ANAF_CLIENT_ID=your_oauth_client_id
ANAF_CLIENT_SECRET=your_oauth_client_secret
ANAF_USE_STAGING=false  # Set to true for testing
```

#### SmartBill
```bash
SMARTBILL_ENABLED=true
SMARTBILL_USERNAME=your_email@example.com
SMARTBILL_TOKEN=your_api_token
SMARTBILL_SEND_EMAIL=true
```

## API Usage

### 1. Fetching Stripe Data

#### Get Stripe Invoices
```bash
# Get invoices for a date range
curl "http://localhost:8000/api/stripe/invoices?start_date=2025-05-20&end_date=2025-05-31&status=paid"

# Filter by customer
curl "http://localhost:8000/api/stripe/invoices?start_date=2025-05-20&end_date=2025-05-31&customer_id=cus_123456"

curl -v "http://localhost:8000/api/stripe/test"
```

Response example:
```json
[
  {
    "id": "in_1234567890",
    "number": "INV-0001",
    "customer_id": "cus_123456",
    "customer_name": "Acme Corp",
    "customer_email": "billing@acme.com",
    "amount_total": 1190.0,
    "currency": "RON",
    "status": "paid",
    "created": "2024-01-15T10:30:00",
    "source_type": "invoice"
  }
]
```

#### Get Stripe Charges (Orders without invoices)
```bash
# Get charges for a date range
curl "http://localhost:8000/api/stripe/charges?start_date=2025-05-20&end_date=2025-05-31&status=succeeded"
```

### 2. Processing Invoices

#### Process Single Invoice/Charge
```bash
# Process a Stripe invoice through ANAF
curl -X POST http://localhost:8000/api/invoices/process \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "stripe_invoice",
    "source_id": "in_1234567890",
    "provider": "anaf",
    "customer_tax_id": "RO12345678"
  }'

# Process a Stripe charge through SmartBill
curl -X POST http://localhost:8000/api/invoices/process \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "stripe_charge",
    "source_id": "ch_1234567890",
    "provider": "smartbill",
    "customer_tax_id": "RO87654321",
    "invoice_number": "FACT-2024-001"
  }'
```

#### Batch Processing
```bash
# Process multiple items at once
curl -X POST http://localhost:8000/api/invoices/process/batch \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "anaf",
    "invoices": [
      {
        "source_type": "stripe_invoice",
        "source_id": "in_123",
        "customer_tax_id": "RO12345678"
      },
      {
        "source_type": "stripe_charge",
        "source_id": "ch_456",
        "customer_tax_id": "RO87654321"
      }
    ]
  }'
```

### 3. Status and Download

#### Check Invoice Status
```bash
curl "http://localhost:8000/api/invoices/status/in_1234567890?provider=anaf"
```

#### Download Processed Invoice
```bash
# Download as PDF
curl -o invoice.pdf "http://localhost:8000/api/invoices/download/12345?provider=anaf&format=pdf"

# Download as XML
curl -o invoice.xml "http://localhost:8000/api/invoices/download/12345?provider=anaf&format=xml"
```

### 4. Company Validation

#### Validate Romanian CUI
```bash
curl -X POST "http://localhost:8000/api/anaf/validate-cui?cui=12345678"
```

#### Lookup Company Information
```bash
curl "http://localhost:8000/api/anaf/company/12345678"
```

Response:
```json
{
  "cui": "12345678",
  "name": "COMPANY NAME SRL",
  "address": "STR. EXAMPLE NR. 1, SECTOR 1",
  "registration_number": "J40/1234/2020",
  "vat_payer": true,
  "vat_registration_date": "2020-01-01"
}
```

## Command Line Tools

### 1. Process Invoices Script

#### Basic Usage
```bash
# Process last 7 days of invoices
python scripts/process_invoices.py --provider anaf --type invoices --days 7

# Process last 30 days of charges
python scripts/process_invoices.py --provider smartbill --type charges --days 30

# Process both invoices and charges
python scripts/process_invoices.py --provider anaf --type both --days 14
```

#### Advanced Options
```bash
# Specific date range
python scripts/process_invoices.py \
  --provider anaf \
  --type invoices \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --output results.json

# Dry run (fetch but don't process)
python scripts/process_invoices.py \
  --provider anaf \
  --type both \
  --days 7 \
  --dry-run

# Custom API endpoint
python scripts/process_invoices.py \
  --provider smartbill \
  --api-url http://api.example.com:8000 \
  --days 1
```

### 2. Customer Sync Script

#### Prepare Customer Mappings
```bash
# Create a CSV file with customer email to CUI mappings
cat > customers.csv << EOF
email,cui
client1@example.com,RO12345678
client2@example.com,RO87654321
billing@company.ro,RO11223344
EOF
```

#### Sync and Validate
```bash
# Basic sync
python scripts/sync_customers.py --mappings customers.csv

# Validate CUIs and lookup company info
python scripts/sync_customers.py \
  --mappings customers.csv \
  --validate \
  --output validated_customers.json

# Check last 60 days of customers
python scripts/sync_customers.py \
  --days 60 \
  --validate \
  --output all_customers.csv
```

## Automation & Scheduling

### 1. Cron Jobs

Add to crontab (`crontab -e`):

```bash
# Process yesterday's invoices every day at 2 AM
0 2 * * * /path/to/venv/bin/python /path/to/scripts/process_invoices.py --provider anaf --days 1 --output /var/log/invoices/$(date +\%Y-\%m-\%d).json

# Weekly customer sync on Sundays at 3 AM
0 3 * * 0 /path/to/venv/bin/python /path/to/scripts/sync_customers.py --days 7 --validate --output /var/log/customers/weekly.json

# Monthly full sync on the 1st at 4 AM
0 4 1 * * /path/to/venv/bin/python /path/to/scripts/process_invoices.py --provider anaf --type both --days 31
```

### 2. Systemd Service

Create `/etc/systemd/system/stripe-invoice-sync.service`:

```ini
[Unit]
Description=Stripe Invoice Sync API
After=network.target

[Service]
Type=exec
User=www-data
WorkingDirectory=/opt/stripe-invoice-sync
Environment="PATH=/opt/stripe-invoice-sync/venv/bin"
ExecStart=/opt/stripe-invoice-sync/venv/bin/python -m app.main
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable stripe-invoice-sync
sudo systemctl start stripe-invoice-sync
```

### 3. Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t stripe-invoice-sync .
docker run -d -p 8000:8000 --env-file .env stripe-invoice-sync
```

## Common Workflows

### 1. Daily Invoice Processing

```bash
#!/bin/bash
# daily_process.sh

# Set date range (yesterday)
START_DATE=$(date -d "yesterday" +%Y-%m-%d)
END_DATE=$(date -d "yesterday" +%Y-%m-%d)

# Process invoices
echo "Processing invoices for $START_DATE..."
python scripts/process_invoices.py \
  --provider anaf \
  --type invoices \
  --start-date $START_DATE \
  --end-date $END_DATE \
  --output logs/invoices_$START_DATE.json

# Process charges
echo "Processing charges for $START_DATE..."
python scripts/process_invoices.py \
  --provider anaf \
  --type charges \
  --start-date $START_DATE \
  --end-date $END_DATE \
  --output logs/charges_$START_DATE.json

# Send summary email (example)
python scripts/send_summary.py --date $START_DATE
```

### 2. Bulk Historical Processing

```bash
#!/bin/bash
# process_historical.sh

# Process 3 months of historical data in weekly batches
for i in {0..12}; do
  START_DAYS=$((i * 7 + 7))
  END_DAYS=$((i * 7))
  
  echo "Processing week $i (${START_DAYS} to ${END_DAYS} days ago)..."
  
  python scripts/process_invoices.py \
    --provider anaf \
    --type both \
    --days 7 \
    --start-date $(date -d "${START_DAYS} days ago" +%Y-%m-%d) \
    --end-date $(date -d "${END_DAYS} days ago" +%Y-%m-%d) \
    --output historical/week_$i.json
  
  # Rate limiting pause
  sleep 30
done
```

### 3. Customer CUI Collection

```python
#!/usr/bin/env python3
# collect_missing_cuis.py

import httpx
import csv
from datetime import datetime, timedelta

# Fetch customers without CUI
async def get_customers_without_cui():
    async with httpx.AsyncClient() as client:
        # Get recent invoices
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)
        
        response = await client.get(
            "http://localhost:8000/api/stripe/invoices",
            params={
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        invoices = response.json()
        
        # Find unique customers without proper CUI
        missing = {}
        for invoice in invoices:
            email = invoice["customer_email"]
            if email and email not in missing:
                # Check if customer has CUI in your records
                # This is simplified - implement actual lookup
                missing[email] = {
                    "name": invoice["customer_name"],
                    "email": email,
                    "sample_invoice": invoice["id"]
                }
        
        return missing

# Save to CSV for manual completion
customers = await get_customers_without_cui()
with open("missing_cuis.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=["email", "name", "cui", "notes"])
    writer.writeheader()
    for email, data in customers.items():
        writer.writerow({
            "email": email,
            "name": data["name"],
            "cui": "",  # To be filled manually
            "notes": f"Sample: {data['sample_invoice']}"
        })

print(f"Found {len(customers)} customers without CUI")
print("Please complete missing_cuis.csv and run sync_customers.py")
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**ANAF OAuth2 Issues:**
```bash
# Test ANAF credentials
curl http://localhost:8000/api/providers/anaf/validate

# Check OAuth2 token endpoint
curl -X POST https://api.anaf.ro/oauth2/token \
  -d "grant_type=client_credentials" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

**SmartBill API Issues:**
```bash
# Test SmartBill credentials
curl http://localhost:8000/api/providers/smartbill/validate

# Manual test
curl -u "email:token" https://ws.smartbill.ro/SBORO/api/company/info?cif=YOUR_CIF
```

#### 2. Missing Customer Tax IDs

```python
# Handle missing CUIs programmatically
response = requests.post(
    "http://localhost:8000/api/invoices/process",
    json={
        "source_type": "stripe_invoice",
        "source_id": "in_123",
        "provider": "anaf",
        "customer_tax_id": "-"  # Use dash for individuals
    }
)
```

#### 3. Rate Limiting

```python
# Add delays in batch processing
import time

for invoice in invoices:
    process_invoice(invoice)
    time.sleep(0.5)  # 500ms delay between requests
```

### Debug Mode

Enable detailed logging:
```bash
# In .env
LOG_LEVEL=DEBUG

# Or via environment
LOG_LEVEL=DEBUG python -m app.main
```

### Health Checks

```bash
# Full system health check
curl http://localhost:8000/health | jq .

# Check specific provider
curl http://localhost:8000/api/providers/ | jq '.[] | select(.name=="anaf")'
```

## Best Practices

1. **Always validate CUIs** before processing invoices
2. **Use batch processing** for better performance
3. **Implement retry logic** for failed invoices
4. **Keep audit logs** of all processed invoices
5. **Regular backups** of processing history
6. **Monitor API rate limits** to avoid throttling
7. **Test with staging** environments first

## Support

For issues or questions:
1. Check the API documentation at `/docs`
2. Review logs in the application directory
3. Validate your configuration with health endpoints
4. Test with minimal examples first