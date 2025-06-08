"""
Stripe service for fetching invoices and charges
"""
import stripe
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import logging
from pydantic import BaseModel
import os

from app.core.provider_interface import InvoiceData
from app.utils.formatters import format_stripe_amount


logger = logging.getLogger(__name__)


class StripeConfig(BaseModel):
    api_key: str
    webhook_secret: Optional[str] = None
    expand_fields: List[str] = ["data.customer", "data.customer.tax_ids", "data.default_tax_rates"]


class StripeDataType(str):
    INVOICE = "invoice"
    CHARGE = "charge"


class StripeService:
    """Service for interacting with Stripe API"""
    
    def __init__(self, config: StripeConfig):
        self.config = config
        stripe.api_key = config.api_key
        
    async def fetch_invoices(
        self,
        start_date: datetime,
        end_date: datetime,
        status: str = "paid",
        limit: int = 100,
        customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch invoices from Stripe"""
        try:
            # Ensure API key is set
            if not self.config.api_key:
                raise ValueError("Stripe API key is not set")
            
            stripe.api_key = self.config.api_key
            
            params = {
                "created": {
                    "gte": int(start_date.timestamp()),
                    "lte": int(end_date.timestamp())
                },
                "status": status,
                "limit": limit,
                "expand": self.config.expand_fields
            }
            
            if customer_id:
                params["customer"] = customer_id
                
            invoices = []
            has_more = True
            
            while has_more:
                response = stripe.Invoice.list(**params)
                invoices.extend(response.data)
                has_more = response.has_more
                
                if has_more:
                    params["starting_after"] = response.data[-1].id
                    
            logger.info(f"Fetched {len(invoices)} invoices from Stripe")
            return [invoice.to_dict() for invoice in invoices]
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching invoices: {str(e)}")
            raise
            
    async def fetch_charges(
        self,
        start_date: datetime,
        end_date: datetime,
        status: str = "succeeded",
        limit: int = 100,
        customer_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch charges (orders) from Stripe"""
        try:
            params = {
                "created": {
                    "gte": int(start_date.timestamp()),
                    "lte": int(end_date.timestamp())
                },
                "status": status,
                "limit": limit,
                "expand": ["data.customer", "data.customer.tax_ids"]
            }
            
            if customer_id:
                params["customer"] = customer_id
                
            charges = []
            has_more = True
            
            while has_more:
                response = stripe.Charge.list(**params)
                charges.extend(response.data)
                has_more = response.has_more
                
                if has_more:
                    params["starting_after"] = response.data[-1].id
                    
            logger.info(f"Fetched {len(charges)} charges from Stripe")
            return [charge.to_dict() for charge in charges]
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error: {str(e)}")
            raise
    
    async def get_invoice_by_id(self, invoice_id: str) -> Dict[str, Any]:
        """Get a specific invoice by ID"""
        try:
            invoice = stripe.Invoice.retrieve(
                invoice_id,
                expand=["customer", "customer.tax_ids", "default_tax_rates"]
            )
            return invoice.to_dict()
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve invoice {invoice_id}: {str(e)}")
            raise
    
    async def get_charge_by_id(self, charge_id: str) -> Dict[str, Any]:
        """Get a specific charge by ID"""
        try:
            charge = stripe.Charge.retrieve(
                charge_id,
                expand=["customer", "customer.tax_ids"]
            )
            return charge.to_dict()
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve charge {charge_id}: {str(e)}")
            raise
    
    def convert_invoice_to_standard_format(
        self,
        stripe_invoice: Dict[str, Any],
        supplier_info: Dict[str, Any]
    ) -> InvoiceData:
        """Convert Stripe invoice to standardized format"""
        
        customer = stripe_invoice.get("customer", {})
        
        # Extract customer tax ID
        customer_tax_id = None
        if isinstance(customer, dict):
            tax_ids_obj = customer.get("tax_ids", {})
            if tax_ids_obj is None:
                tax_ids_obj = {}
            tax_ids = tax_ids_obj.get("data", [])
            if tax_ids:
                customer_tax_id = tax_ids[0].get("value")
        
        # Extract customer address
        customer_address = None
        if isinstance(customer, dict) and customer.get("address"):
            addr = customer["address"]
            customer_address = {
                "line1": addr.get("line1", ""),
                "line2": addr.get("line2", ""),
                "city": addr.get("city", ""),
                "state": addr.get("state", ""),
                "postal_code": addr.get("postal_code", ""),
                "country": addr.get("country", "RO")
            }
        
        # Process invoice lines
        lines = []
        lines_data = stripe_invoice.get("lines", {})
        if lines_data is None:
            lines_data = {}
        for line_item in lines_data.get("data", []):
            lines.append({
                "description": line_item.get("description", ""),
                "quantity": line_item.get("quantity", 1),
                "unit_price": format_stripe_amount(
                    line_item.get("unit_amount_decimal", line_item.get("amount", 0)),
                    stripe_invoice.get("currency", "ron")
                ),
                "amount": format_stripe_amount(
                    line_item.get("amount", 0),
                    stripe_invoice.get("currency", "ron")
                ),
                "tax_rate": self._extract_tax_rate(line_item),
                "metadata": line_item.get("metadata", {})
            })
        
        # Calculate totals
        subtotal = format_stripe_amount(
            stripe_invoice.get("subtotal", 0),
            stripe_invoice.get("currency", "ron")
        )
        tax_amount = format_stripe_amount(
            stripe_invoice.get("tax", 0),
            stripe_invoice.get("currency", "ron")
        )
        total = format_stripe_amount(
            stripe_invoice.get("total", 0),
            stripe_invoice.get("currency", "ron")
        )
        amount_paid = format_stripe_amount(
            stripe_invoice.get("amount_paid", 0),
            stripe_invoice.get("currency", "ron")
        )
        
        return InvoiceData(
            provider_invoice_id=stripe_invoice.get("number"),
            invoice_number=stripe_invoice.get("number"),
            invoice_date=datetime.fromtimestamp(stripe_invoice["created"]),
            due_date=datetime.fromtimestamp(stripe_invoice["due_date"]) if stripe_invoice.get("due_date") else None,
            currency=stripe_invoice.get("currency", "ron").upper(),
            source_type=StripeDataType.INVOICE,
            source_id=stripe_invoice["id"],
            source_data=stripe_invoice,
            customer_id=customer.get("id", "") if isinstance(customer, dict) else str(customer),
            customer_name=(customer.get("name") or "") if isinstance(customer, dict) else "",
            customer_email=(customer.get("email") or "") if isinstance(customer, dict) else "",
            customer_tax_id=customer_tax_id,
            customer_address=customer_address,
            customer_country=(customer.get("address", {}) or {}).get("country", "RO") if isinstance(customer, dict) else "RO",
            supplier_name=supplier_info["name"],
            supplier_tax_id=supplier_info["tax_id"],
            supplier_address=supplier_info["address"],
            supplier_registration=supplier_info.get("registration"),
            lines=lines,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=total,
            amount_paid=amount_paid,
            tax_rate=self._calculate_average_tax_rate(subtotal, tax_amount),
            tax_breakdown=self._extract_tax_breakdown(stripe_invoice),
            metadata=stripe_invoice.get("metadata", {})
        )
    
    def convert_charge_to_standard_format(
        self,
        stripe_charge: Dict[str, Any],
        supplier_info: Dict[str, Any]
    ) -> InvoiceData:
        """Convert Stripe charge to standardized format"""
        customer = stripe_charge.get("customer", {})
        
        # Extract customer info from various sources
        customer_name = ""
        customer_email = ""
        customer_tax_id = None
        customer_address = None
        
        # Try to get from customer object
        if isinstance(customer, dict):
            customer_name = customer.get("name") or ""
            customer_email = customer.get("email") or ""
            
            tax_ids_obj = customer.get("tax_ids", {})
            if tax_ids_obj is None:
                tax_ids_obj = {}
            tax_ids = tax_ids_obj.get("data", [])
            if tax_ids:
                customer_tax_id = tax_ids[0].get("value")
                
            if customer.get("address"):
                addr = customer["address"]
                customer_address = {
                    "line1": addr.get("line1", ""),
                    "line2": addr.get("line2", ""),
                    "city": addr.get("city", ""),
                    "state": addr.get("state", ""),
                    "postal_code": addr.get("postal_code", ""),
                    "country": addr.get("country", "RO")
                }
        
        # Fall back to billing details
        billing_details = stripe_charge.get("billing_details", {})
        if not customer_name and billing_details.get("name"):
            customer_name = billing_details["name"]
        if not customer_email and billing_details.get("email"):
            customer_email = billing_details["email"]
        if not customer_address and billing_details.get("address"):
            addr = billing_details["address"]
            customer_address = {
                "line1": addr.get("line1", ""),
                "line2": addr.get("line2", ""),
                "city": addr.get("city", ""),
                "state": addr.get("state", ""),
                "postal_code": addr.get("postal_code", ""),
                "country": addr.get("country", "RO")
            }
        
        # Fall back to metadata
        metadata = stripe_charge.get("metadata", {})
        if not customer_name and metadata.get("customer_name"):
            customer_name = metadata["customer_name"]
        if not customer_tax_id and metadata.get("tax_id"):
            customer_tax_id = metadata["tax_id"]
        
        # Fall back to receipt email
        if not customer_email:
            customer_email = stripe_charge.get("receipt_email", "")
        
        # Create a single line item from the charge
        amount = format_stripe_amount(
            stripe_charge.get("amount", 0),
            stripe_charge.get("currency", "ron")
        )
        
        description = stripe_charge.get("description", "")
        if not description:
            description = f"Payment - {stripe_charge.get('id', '')}"
        
        # Assume tax is included in the amount (19% VAT)
        tax_rate = supplier_info.get("default_tax_rate", 19.0)
        subtotal = amount / (1 + tax_rate / 100)
        tax_amount = amount - subtotal
        
        lines = [{
            "description": description,
            "quantity": 1,
            "unit_price": subtotal,
            "amount": subtotal,
            "tax_rate": tax_rate,
            "metadata": {}
        }]
        
        return InvoiceData(
            invoice_date=datetime.fromtimestamp(stripe_charge["created"]),
            currency=stripe_charge.get("currency", "ron").upper(),
            source_type=StripeDataType.CHARGE,
            source_id=stripe_charge["id"],
            source_data=stripe_charge,
            customer_id=customer.get("id", "") if isinstance(customer, dict) else str(customer),
            customer_name=customer_name,
            customer_email=customer_email,
            customer_tax_id=customer_tax_id,
            customer_address=customer_address,
            customer_country=(customer_address or {}).get("country", "RO"),
            supplier_name=supplier_info["name"],
            supplier_tax_id=supplier_info["tax_id"],
            supplier_address=supplier_info["address"],
            supplier_registration=supplier_info.get("registration"),
            lines=lines,
            subtotal=round(subtotal, 2),
            tax_amount=round(tax_amount, 2),
            total=amount,
            amount_paid=amount,
            tax_rate=tax_rate,
            metadata=metadata
        )
    
    def _extract_tax_rate(self, line_item: Dict[str, Any]) -> float:
        """Extract tax rate from line item"""
        tax_rates = line_item.get("tax_rates", [])
        if tax_rates:
            return float(tax_rates[0].get("percentage", 0))
        return 0.0
    
    def _calculate_average_tax_rate(self, subtotal: float, tax_amount: float) -> float:
        """Calculate average tax rate"""
        if subtotal > 0:
            return round((tax_amount / subtotal) * 100, 2)
        return 0.0
    
    def _extract_tax_breakdown(self, invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tax breakdown from invoice"""
        breakdown = []
        
        # From total_tax_amounts
        for tax in invoice.get("total_tax_amounts", []):
            breakdown.append({
                "amount": format_stripe_amount(tax.get("amount", 0), invoice.get("currency", "ron")),
                "inclusive": tax.get("inclusive", False),
                "tax_rate": tax.get("tax_rate", {}).get("percentage", 0)
            })
        
        # From default_tax_rates
        if not breakdown and invoice.get("tax"):
            tax_amount = format_stripe_amount(invoice.get("tax", 0), invoice.get("currency", "ron"))
            breakdown.append({
                "amount": tax_amount,
                "inclusive": False,
                "tax_rate": 19.0  # Default Romanian VAT
            })
            
        return breakdown