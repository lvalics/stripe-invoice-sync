"""
SmartBill provider implementation
"""
import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import base64

from app.core.provider_interface import (
    InvoiceProviderInterface,
    ProviderConfig,
    InvoiceData,
    ProviderResponse,
    InvoiceStatus
)


logger = logging.getLogger(__name__)


class SmartBillProvider(InvoiceProviderInterface):
    """SmartBill provider implementation"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = config.api_endpoint or "https://ws.smartbill.ro/SBORO/api"
        self.username = config.credentials.get("username")
        self.token = config.credentials.get("token")
        self.company_cif = config.credentials.get("company_cif")
        
        # Create auth header
        auth_string = f"{self.username}:{self.token}"
        self.auth_header = f"Basic {base64.b64encode(auth_string.encode()).decode()}"
        
    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate SmartBill credentials"""
        try:
            logger.error(f"Validating SmartBill credentials for CIF: {self.company_cif}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/company/info",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json"
                    },
                    params={"cif": self.company_cif}
                )
                
                logger.error(f"SmartBill validation response: {response.status_code}")
                
                if response.status_code == 200:
                    return {
                        "valid": True,
                        "message": "SmartBill credentials validated successfully"
                    }
                else:
                    return {
                        "valid": False,
                        "message": f"Authentication failed with status {response.status_code}"
                    }
                
        except Exception as e:
            logger.error(f"SmartBill credential validation failed: {str(e)}")
            return {
                "valid": False,
                "message": f"Connection error: {str(e)}"
            }
    
    async def create_invoice(self, invoice_data: InvoiceData) -> ProviderResponse:
        """Create invoice in SmartBill system"""
        try:
            # Validate invoice data
            errors = self.validate_invoice_data(invoice_data)
            if errors:
                return ProviderResponse(
                    success=False,
                    provider=self.name,
                    status=InvoiceStatus.ERROR,
                    errors=errors
                )
            
            # Transform to SmartBill format
            smartbill_data = self.transform_to_provider_format(invoice_data)
            
            logger.error(f"SmartBill payload: {smartbill_data}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/invoice",
                    json=smartbill_data,
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )
                
                logger.error(f"SmartBill response status: {response.status_code}")
                logger.error(f"SmartBill response: {response.text}")
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    return ProviderResponse(
                        success=True,
                        provider=self.name,
                        invoice_id=invoice_data.source_id,
                        external_id=str(result.get("number", "")),
                        status=InvoiceStatus.SENT,
                        message=f"Invoice created successfully: {result.get('series', '')}{result.get('number', '')}",
                        data=result
                    )
                else:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", f"Failed to create invoice (status {response.status_code})")
                    except:
                        # Check for common HTTP status codes
                        if response.status_code == 500:
                            error_msg = "SmartBill server error. Please check invoice data (price cannot be 0) and try again."
                        elif response.status_code == 401:
                            error_msg = "SmartBill authentication failed. Please check credentials."
                        elif response.status_code == 400:
                            error_msg = "Invalid invoice data sent to SmartBill."
                        else:
                            error_msg = f"SmartBill API error (status {response.status_code})"
                        error_data = {"status_code": response.status_code}
                    
                    logger.error(f"SmartBill error: {error_msg}")
                    
                    return ProviderResponse(
                        success=False,
                        provider=self.name,
                        status=InvoiceStatus.ERROR,
                        errors=[error_msg],
                        data=error_data
                    )
                    
        except Exception as e:
            logger.error(f"Failed to create SmartBill invoice: {str(e)}")
            return ProviderResponse(
                success=False,
                provider=self.name,
                status=InvoiceStatus.ERROR,
                errors=[str(e)]
            )
    
    async def get_invoice_status(self, invoice_id: str) -> ProviderResponse:
        """Get status of a previously created invoice"""
        try:
            # SmartBill doesn't have a direct status endpoint
            # We'll return success with sent status
            return ProviderResponse(
                success=True,
                provider=self.name,
                invoice_id=invoice_id,
                status=InvoiceStatus.SENT,
                message="SmartBill invoices are sent immediately upon creation"
            )
            
        except Exception as e:
            logger.error(f"Failed to get SmartBill invoice status: {str(e)}")
            return ProviderResponse(
                success=False,
                provider=self.name,
                status=InvoiceStatus.ERROR,
                errors=[str(e)]
            )
    
    async def download_invoice(self, invoice_id: str, format: str = "pdf") -> Optional[bytes]:
        """Download invoice from SmartBill"""
        try:
            # Parse series and number from invoice_id
            parts = invoice_id.split("-")
            if len(parts) < 2:
                return None
                
            series = parts[0]
            number = parts[1]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/invoice/pdf",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/pdf"
                    },
                    params={
                        "cif": self.company_cif,
                        "seriesname": series,
                        "number": number
                    }
                )
                
                if response.status_code == 200:
                    return response.content
                    
            return None
            
        except Exception as e:
            logger.error(f"Failed to download SmartBill invoice: {str(e)}")
            return None
    
    async def cancel_invoice(self, invoice_id: str) -> ProviderResponse:
        """Cancel an invoice in SmartBill"""
        try:
            # Parse series and number from invoice_id
            parts = invoice_id.split("-")
            if len(parts) < 2:
                return ProviderResponse(
                    success=False,
                    provider=self.name,
                    status=InvoiceStatus.ERROR,
                    errors=["Invalid invoice ID format"]
                )
                
            series = parts[0]
            number = parts[1]
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/invoice",
                    headers={
                        "Authorization": self.auth_header,
                        "Accept": "application/json"
                    },
                    params={
                        "cif": self.company_cif,
                        "seriesname": series,
                        "number": number
                    }
                )
                
                if response.status_code == 200:
                    return ProviderResponse(
                        success=True,
                        provider=self.name,
                        invoice_id=invoice_id,
                        status=InvoiceStatus.CANCELLED,
                        message="Invoice cancelled successfully"
                    )
                else:
                    return ProviderResponse(
                        success=False,
                        provider=self.name,
                        status=InvoiceStatus.ERROR,
                        errors=["Failed to cancel invoice"]
                    )
                    
        except Exception as e:
            logger.error(f"Failed to cancel SmartBill invoice: {str(e)}")
            return ProviderResponse(
                success=False,
                provider=self.name,
                status=InvoiceStatus.ERROR,
                errors=[str(e)]
            )
    
    async def get_company_info(self, tax_id: str) -> Optional[Dict[str, Any]]:
        """Get company information (not directly supported by SmartBill)"""
        # SmartBill doesn't provide company lookup
        # Could integrate with ANAF for this
        return None
    
    def transform_to_provider_format(self, invoice_data: InvoiceData) -> Dict[str, Any]:
        """Transform standardized invoice data to SmartBill format"""
        # Calculate due days
        due_days = 0
        if invoice_data.due_date:
            due_days = (invoice_data.due_date - invoice_data.invoice_date).days
        
        # Transform lines
        products = []
        for line in invoice_data.lines:
            # Determine tax name based on percentage
            tax_percentage = line.get("tax_rate", 19)
            if tax_percentage == 0:
                tax_name = "Scutit"
            elif tax_percentage in [5, 9]:
                tax_name = "Redusa"
            else:
                tax_name = "Normala"
            
            # Ensure price is never 0
            unit_price = line["unit_price"]
            if unit_price <= 0:
                logger.warning(f"Zero or negative price detected for line: {line['description']}")
                unit_price = 0.01  # Set minimal price to avoid 500 error
            
            product_data = {
                "name": line["description"][:200],  # Limit to 200 chars
                "quantity": float(line["quantity"]),
                "price": float(unit_price),
                "measuringUnitName": line.get("unit", "buc"),
                "taxName": tax_name,
                "taxPercentage": float(tax_percentage),
                "isService": True,
                "isTaxIncluded": False
            }
            
            # Don't include fields that might cause issues
            # No: code, description, discount, discountType, saveToDb, warehouseName
            
            products.append(product_data)
        
        # Build SmartBill invoice object
        smartbill_data = {
            "companyVatCode": self.company_cif,
            "client": {
                "name": invoice_data.customer_name[:200],  # Limit to 200 chars
                "vatCode": invoice_data.customer_tax_id or "-",
                "email": invoice_data.customer_email,
                "address": self._format_address(invoice_data.customer_address) or "N/A",
                "isTaxPayer": bool(invoice_data.customer_tax_id and invoice_data.customer_tax_id != "-"),
                "city": invoice_data.customer_address.get("city", "București") if invoice_data.customer_address else "București",
                "country": invoice_data.customer_country or "Romania"
                # No saveToDb field - it causes 500 errors
            },
            "issueDate": invoice_data.invoice_date.strftime("%Y-%m-%d"),
            "seriesName": self.config.options.get("invoice_series", "FACT"),
            "isDraft": False,
            "dueDate": invoice_data.due_date.strftime("%Y-%m-%d") if invoice_data.due_date else (invoice_data.invoice_date + timedelta(days=due_days)).strftime("%Y-%m-%d"),
            "deliveryDate": invoice_data.invoice_date.strftime("%Y-%m-%d"),
            "currency": invoice_data.currency,
            "exchangeRate": float(self.config.options.get("exchange_rate", 1.0)),
            "language": "RO",
            "products": products,
            "observations": f"Stripe ID: {invoice_data.source_id}"
        }
        
        # Don't include problematic fields that cause 500 errors:
        # No: precision, useStock, payment, paymentSeries, issueInvoiceOrReceipt,
        #     usePaymentTax, useEstimateDetails, internalNotes, showPaymentTax,
        #     daysUntilDue, sendEmail
        
        return smartbill_data
    
    def validate_invoice_data(self, invoice_data: InvoiceData) -> List[str]:
        """Validate invoice data for SmartBill requirements"""
        errors = super().validate_invoice_data(invoice_data)
        
        # SmartBill-specific validations
        if not invoice_data.customer_email:
            errors.append("Customer email is required for SmartBill")
            
        # Check for valid currency
        valid_currencies = ["RON", "EUR", "USD", "GBP"]
        if invoice_data.currency not in valid_currencies:
            errors.append(f"Currency {invoice_data.currency} not supported by SmartBill")
        
        return errors
    
    def _format_address(self, address: Optional[Dict[str, str]]) -> str:
        """Format address for SmartBill"""
        if not address:
            return ""
            
        parts = []
        if address.get("line1"):
            parts.append(address["line1"])
        if address.get("line2"):
            parts.append(address["line2"])
        if address.get("postal_code"):
            parts.append(address["postal_code"])
            
        return ", ".join(parts)