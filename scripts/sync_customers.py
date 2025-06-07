#!/usr/bin/env python3
"""
Script to sync customer tax IDs between Stripe and local database
"""
import asyncio
import argparse
import logging
import csv
import json
from typing import Dict, List, Any
import httpx
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CustomerSync:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.cui_mappings = {}
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def load_mappings(self, filepath: str):
        """Load CUI mappings from CSV file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get('email', '').strip().lower()
                    cui = row.get('cui', '').strip()
                    if email and cui:
                        self.cui_mappings[email] = cui
            logger.info(f"Loaded {len(self.cui_mappings)} CUI mappings")
        except Exception as e:
            logger.error(f"Failed to load mappings: {e}")
    
    async def fetch_customers_from_invoices(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch unique customers from recent invoices"""
        customers = {}
        
        # Fetch from invoices
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "status": "paid"
        }
        response = await self.client.get(
            f"{self.api_url}/api/stripe/invoices",
            params=params
        )
        response.raise_for_status()
        invoices = response.json()
        
        for invoice in invoices:
            email = invoice.get("customer_email", "").lower()
            if email and email not in customers:
                customers[email] = {
                    "id": invoice.get("customer_id"),
                    "name": invoice.get("customer_name"),
                    "email": email,
                    "cui": None
                }
        
        logger.info(f"Found {len(customers)} unique customers from invoices")
        return customers
    
    async def validate_cui(self, cui: str) -> Dict[str, Any]:
        """Validate CUI format via API"""
        response = await self.client.post(
            f"{self.api_url}/api/anaf/validate-cui",
            params={"cui": cui}
        )
        response.raise_for_status()
        return response.json()
    
    async def lookup_company(self, cui: str) -> Dict[str, Any]:
        """Lookup company info from ANAF"""
        try:
            response = await self.client.get(
                f"{self.api_url}/api/anaf/company/{cui}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def process_customers(
        self,
        customers: Dict[str, Dict[str, Any]],
        validate: bool = True
    ) -> List[Dict[str, Any]]:
        """Process customers and add CUI information"""
        results = []
        
        for email, customer in customers.items():
            result = customer.copy()
            
            # Check if we have a CUI mapping
            if email in self.cui_mappings:
                cui = self.cui_mappings[email]
                result["cui"] = cui
                result["cui_source"] = "mapping"
                
                if validate:
                    # Validate CUI
                    validation = await self.validate_cui(cui)
                    result["cui_valid"] = validation["valid"]
                    
                    if validation["valid"]:
                        # Lookup company info
                        company = await self.lookup_company(validation["formatted"])
                        if company:
                            result["company_name"] = company["name"]
                            result["company_address"] = company["address"]
                            result["vat_payer"] = company["vat_payer"]
            else:
                result["cui_source"] = "missing"
                result["cui_valid"] = False
            
            results.append(result)
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], format: str, filename: str):
        """Save results to file"""
        output_path = Path(filename)
        
        if format == "json":
            with open(output_path, "w", encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        elif format == "csv":
            if results:
                keys = results[0].keys()
                with open(output_path, "w", encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(results)
        
        logger.info(f"Results saved to {output_path}")
    
    def print_summary(self, results: List[Dict[str, Any]]):
        """Print summary statistics"""
        total = len(results)
        with_cui = sum(1 for r in results if r.get("cui"))
        valid_cui = sum(1 for r in results if r.get("cui_valid"))
        vat_payers = sum(1 for r in results if r.get("vat_payer"))
        
        print("\n=== Customer Summary ===")
        print(f"Total customers: {total}")
        print(f"With CUI: {with_cui} ({with_cui/total*100:.1f}%)")
        print(f"Valid CUI: {valid_cui} ({valid_cui/total*100:.1f}%)")
        print(f"VAT payers: {vat_payers} ({vat_payers/total*100:.1f}%)")
        
        # Show customers without CUI
        missing = [r for r in results if not r.get("cui")]
        if missing:
            print(f"\nCustomers without CUI ({len(missing)}):")
            for customer in missing[:10]:  # Show first 10
                print(f"  - {customer['email']} ({customer.get('name', 'No name')})")
            if len(missing) > 10:
                print(f"  ... and {len(missing) - 10} more")


async def main():
    parser = argparse.ArgumentParser(
        description="Sync and validate customer tax IDs"
    )
    parser.add_argument(
        "--mappings",
        help="CSV file with email,cui mappings"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate CUIs and lookup company info"
    )
    parser.add_argument(
        "--output",
        help="Output file (JSON or CSV based on extension)"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API URL"
    )
    
    args = parser.parse_args()
    
    async with CustomerSync(args.api_url) as sync:
        # Load mappings if provided
        if args.mappings:
            sync.load_mappings(args.mappings)
        
        # Calculate date range
        from datetime import datetime, timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=args.days)
        
        # Fetch customers
        logger.info(f"Fetching customers from {start_date} to {end_date}")
        customers = await sync.fetch_customers_from_invoices(
            str(start_date),
            str(end_date)
        )
        
        # Process customers
        logger.info("Processing customers...")
        results = await sync.process_customers(customers, args.validate)
        
        # Save results
        if args.output:
            format = "csv" if args.output.endswith(".csv") else "json"
            sync.save_results(results, format, args.output)
        
        # Print summary
        sync.print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())