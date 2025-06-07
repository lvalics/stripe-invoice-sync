#!/usr/bin/env python3
"""
Script to automatically process Stripe invoices through configured providers
"""
import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import httpx
import json
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class InvoiceProcessor:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def check_health(self) -> Dict[str, Any]:
        """Check API health and provider status"""
        response = await self.client.get(f"{self.api_url}/health")
        response.raise_for_status()
        return response.json()
    
    async def fetch_stripe_invoices(
        self,
        start_date: str,
        end_date: str,
        status: str = "paid"
    ) -> List[Dict[str, Any]]:
        """Fetch invoices from Stripe"""
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "status": status
        }
        response = await self.client.get(
            f"{self.api_url}/api/stripe/invoices",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def fetch_stripe_charges(
        self,
        start_date: str,
        end_date: str,
        status: str = "succeeded"
    ) -> List[Dict[str, Any]]:
        """Fetch charges from Stripe"""
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "status": status
        }
        response = await self.client.get(
            f"{self.api_url}/api/stripe/charges",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def process_invoice(
        self,
        source_type: str,
        source_id: str,
        provider: str,
        customer_tax_id: str = None
    ) -> Dict[str, Any]:
        """Process a single invoice"""
        data = {
            "source_type": source_type,
            "source_id": source_id,
            "provider": provider
        }
        if customer_tax_id:
            data["customer_tax_id"] = customer_tax_id
            
        response = await self.client.post(
            f"{self.api_url}/api/invoices/process",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    async def process_batch(
        self,
        items: List[Dict[str, Any]],
        provider: str,
        source_type: str
    ) -> List[Dict[str, Any]]:
        """Process multiple items"""
        results = []
        
        for item in items:
            logger.info(f"Processing {source_type} {item['id']}...")
            try:
                result = await self.process_invoice(
                    source_type=f"stripe_{source_type}",
                    source_id=item["id"],
                    provider=provider,
                    customer_tax_id=self._extract_tax_id(item)
                )
                results.append(result)
                
                if result["status"] == "error":
                    logger.error(f"Failed: {result.get('errors', [])}")
                else:
                    logger.info(f"Success: {result.get('message', 'Processed')}")
                    
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing {item['id']}: {str(e)}")
                results.append({
                    "source_id": item["id"],
                    "status": "error",
                    "errors": [str(e)]
                })
        
        return results
    
    def _extract_tax_id(self, item: Dict[str, Any]) -> str:
        """Extract tax ID from invoice/charge data"""
        # This is simplified - in real implementation would parse the full data
        return None
    
    def save_results(self, results: List[Dict[str, Any]], filename: str):
        """Save processing results to file"""
        output_path = Path(filename)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {output_path}")


async def main():
    parser = argparse.ArgumentParser(
        description="Process Stripe invoices through invoice providers"
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=["anaf", "smartbill"],
        help="Invoice provider to use"
    )
    parser.add_argument(
        "--type",
        choices=["invoices", "charges", "both"],
        default="invoices",
        help="Type of Stripe data to process"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)"
    )
    parser.add_argument(
        "--start-date",
        help="Start date (YYYY-MM-DD). Overrides --days"
    )
    parser.add_argument(
        "--end-date",
        help="End date (YYYY-MM-DD). Defaults to today"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API URL"
    )
    parser.add_argument(
        "--output",
        help="Output file for results (JSON)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't process"
    )
    
    args = parser.parse_args()
    
    # Calculate date range
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    else:
        end_date = datetime.now().date()
    
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    else:
        start_date = end_date - timedelta(days=args.days)
    
    logger.info(f"Processing {args.type} from {start_date} to {end_date}")
    logger.info(f"Using provider: {args.provider}")
    
    async with InvoiceProcessor(args.api_url) as processor:
        # Check health
        try:
            health = await processor.check_health()
            provider_status = health["providers"].get(args.provider, {})
            if provider_status.get("status") != "connected":
                logger.error(f"Provider {args.provider} is not connected")
                return
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return
        
        all_results = []
        
        # Process invoices
        if args.type in ["invoices", "both"]:
            logger.info("Fetching Stripe invoices...")
            invoices = await processor.fetch_stripe_invoices(
                str(start_date),
                str(end_date)
            )
            logger.info(f"Found {len(invoices)} invoices")
            
            if not args.dry_run and invoices:
                logger.info("Processing invoices...")
                results = await processor.process_batch(
                    invoices,
                    args.provider,
                    "invoice"
                )
                all_results.extend(results)
        
        # Process charges
        if args.type in ["charges", "both"]:
            logger.info("Fetching Stripe charges...")
            charges = await processor.fetch_stripe_charges(
                str(start_date),
                str(end_date)
            )
            logger.info(f"Found {len(charges)} charges")
            
            if not args.dry_run and charges:
                logger.info("Processing charges...")
                results = await processor.process_batch(
                    charges,
                    args.provider,
                    "charge"
                )
                all_results.extend(results)
        
        # Save results
        if args.output and all_results:
            processor.save_results(all_results, args.output)
        
        # Summary
        if all_results:
            success_count = sum(1 for r in all_results if r["status"] != "error")
            error_count = len(all_results) - success_count
            logger.info(f"\nProcessing complete:")
            logger.info(f"  Successful: {success_count}")
            logger.info(f"  Failed: {error_count}")
            logger.info(f"  Total: {len(all_results)}")


if __name__ == "__main__":
    asyncio.run(main())