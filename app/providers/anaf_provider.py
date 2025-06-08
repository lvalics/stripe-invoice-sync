"""
ANAF e-Factura provider implementation
"""
import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import xml.etree.ElementTree as ET
from lxml import etree
import base64
import json
import warnings
import urllib3

# Suppress SSL warnings temporarily
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

from app.core.provider_interface import (
    InvoiceProviderInterface,
    ProviderConfig,
    InvoiceData,
    ProviderResponse,
    InvoiceStatus
)
from app.utils.xml_generator import ANAFXMLGenerator


logger = logging.getLogger(__name__)


class ANAFProvider(InvoiceProviderInterface):
    """ANAF e-Factura provider implementation"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = config.api_endpoint or "https://api.anaf.ro"
        self.staging_url = "https://api-test.anaf.ro"
        self.use_staging = config.options.get("use_staging", False)
        self.xml_generator = ANAFXMLGenerator()
        
        # OAuth2 credentials
        self.client_id = config.credentials.get("client_id")
        self.client_secret = config.credentials.get("client_secret")
        self.access_token = None
        self.token_expires = None
        
    async def validate_credentials(self) -> Dict[str, Any]:
        """Validate ANAF OAuth2 credentials"""
        try:
            await self._ensure_authenticated()
            return {
                "valid": True,
                "message": "ANAF credentials validated successfully"
            }
        except Exception as e:
            logger.error(f"ANAF credential validation failed: {str(e)}")
            return {
                "valid": False,
                "message": f"Authentication failed: {str(e)}"
            }
    
    async def create_invoice(self, invoice_data: InvoiceData) -> ProviderResponse:
        """Create invoice in ANAF e-Factura system"""
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
            
            # Generate XML
            xml_content = self.xml_generator.generate_invoice_xml(invoice_data)
            
            # Upload to ANAF
            upload_response = await self._upload_invoice(
                xml_content=xml_content,
                cui=invoice_data.supplier_tax_id.replace("RO", ""),
                customer_cui=invoice_data.customer_tax_id,
                b2c=invoice_data.customer_tax_id is None or invoice_data.customer_tax_id == "-"
            )
            
            if upload_response["success"]:
                return ProviderResponse(
                    success=True,
                    provider=self.name,
                    invoice_id=invoice_data.source_id,
                    external_id=upload_response["upload_index"],
                    status=InvoiceStatus.SENT,
                    message=f"Invoice uploaded successfully. Index: {upload_response['upload_index']}",
                    data=upload_response
                )
            else:
                return ProviderResponse(
                    success=False,
                    provider=self.name,
                    status=InvoiceStatus.ERROR,
                    errors=[upload_response.get("message", "Upload failed")],
                    data=upload_response
                )
                
        except Exception as e:
            logger.error(f"Failed to create ANAF invoice: {str(e)}")
            return ProviderResponse(
                success=False,
                provider=self.name,
                status=InvoiceStatus.ERROR,
                errors=[str(e)]
            )
    
    async def get_invoice_status(self, invoice_id: str) -> ProviderResponse:
        """Get status of a previously created invoice"""
        try:
            await self._ensure_authenticated()
            
            # Get messages from ANAF
            messages = await self._get_messages(days=7)
            
            # Find message related to this invoice
            for message in messages:
                if invoice_id in message.get("detalii", "") or invoice_id in message.get("id_solicitare", ""):
                    status = self._map_message_to_status(message)
                    return ProviderResponse(
                        success=True,
                        provider=self.name,
                        invoice_id=invoice_id,
                        external_id=message.get("id"),
                        status=status,
                        message=message.get("detalii", ""),
                        data=message
                    )
            
            return ProviderResponse(
                success=True,
                provider=self.name,
                invoice_id=invoice_id,
                status=InvoiceStatus.PENDING,
                message="Invoice is being processed"
            )
            
        except Exception as e:
            logger.error(f"Failed to get ANAF invoice status: {str(e)}")
            return ProviderResponse(
                success=False,
                provider=self.name,
                status=InvoiceStatus.ERROR,
                errors=[str(e)]
            )
    
    async def download_invoice(self, invoice_id: str, format: str = "pdf") -> Optional[bytes]:
        """Download invoice from ANAF"""
        try:
            await self._ensure_authenticated()
            
            # Get download URL from messages
            messages = await self._get_messages(days=30)
            
            for message in messages:
                if message.get("id") == invoice_id:
                    # Download the file
                    content = await self._download_file(message["id"])
                    
                    if format == "pdf" and content:
                        # Convert XML to PDF if needed
                        return await self._convert_xml_to_pdf(content)
                    
                    return content
            
            return None
            
        except httpx.HTTPError as e:
            logger.error(f"ANAF HTTP error during download: {str(e)}")
            raise Exception(f"Connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to download ANAF invoice: {str(e)}")
            # Re-raise to let endpoint handle it
            raise
    
    async def cancel_invoice(self, invoice_id: str) -> ProviderResponse:
        """Cancel an invoice (not directly supported by ANAF)"""
        return ProviderResponse(
            success=False,
            provider=self.name,
            status=InvoiceStatus.ERROR,
            errors=["Invoice cancellation not supported by ANAF. Create a credit note instead."]
        )
    
    async def get_company_info(self, tax_id: str) -> Optional[Dict[str, Any]]:
        """Get company information from ANAF"""
        # Remove RO prefix if present
        cui = tax_id.replace("RO", "").strip()
        logger.info(f"Looking up CUI: {cui}")
        
        try:
            
            # Create a fresh client for each request to avoid connection reuse issues
            limits = httpx.Limits(
                max_keepalive_connections=0,  # Disable connection pooling
                max_connections=1,
                keepalive_expiry=0
            )
            async with httpx.AsyncClient(
                verify=False, 
                limits=limits,
                follow_redirects=True,
                http2=False,  # Disable HTTP/2 which can cause issues
                default_encoding='utf-8'
            ) as client:
                response = await client.post(
                    f"https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva",
                    json=[{
                        "cui": int(cui),
                        "data": datetime.now().strftime("%Y-%m-%d")
                    }],
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Connection": "close",  # Force connection close
                        "Accept-Encoding": "gzip, deflate"  # Explicit encoding
                    },
                    timeout=httpx.Timeout(30.0, connect=10.0, read=20.0)
                )
                logger.info(f"ANAF response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        # Read content once and parse
                        content = await response.aread()
                        data = json.loads(content)
                        logger.info(f"ANAF response data keys: {list(data.keys()) if data else 'None'}")
                    except Exception as json_err:
                        logger.error(f"Failed to parse ANAF JSON response: {json_err}")
                        raise Exception(f"Invalid JSON response from ANAF: {str(json_err)}")
                    finally:
                        # Explicitly close the response
                        await response.aclose()
                    
                    # v9 API may or may not have wrapper structure
                    if "cod" in data and "message" in data:
                        if data.get("cod") != 200:
                            raise Exception(f"ANAF API error: {data.get('message', 'Unknown error')}")
                        logger.info(f"ANAF v9 response with wrapper: cod={data.get('cod')}, message={data.get('message')}")
                    
                    if data.get("found") and len(data.get("found", [])) > 0:
                        company = data["found"][0]
                        logger.info(f"Found company data keys: {list(company.keys())}")
                        
                        # v9 API has nested structure
                        general_data = company.get("date_generale", {})
                        vat_data = company.get("inregistrare_scop_Tva", {})
                        inactive_data = company.get("stare_inactiv", {})
                        
                        logger.info(f"Extracted general_data: {general_data.get('denumire')}")
                        
                        # Extract VAT registration date from periods
                        vat_reg_date = None
                        if vat_data.get("perioade_TVA"):
                            vat_reg_date = vat_data["perioade_TVA"][0].get("data_inceput_ScpTVA")
                        
                        result = {
                            "cui": str(general_data.get("cui")),  # Convert int to string
                            "name": general_data.get("denumire"),
                            "address": general_data.get("adresa"),
                            "registration_number": general_data.get("nrRegCom"),
                            "phone": general_data.get("telefon"),
                            "vat_payer": vat_data.get("scpTVA", False),
                            "vat_registration_date": vat_reg_date,
                            "status": "ACTIV" if not inactive_data.get("statusInactivi", False) else "INACTIV"  # Convert bool to string
                            # Removed raw_data to avoid potential serialization issues
                        }
                        logger.info(f"Returning company info for CUI {cui}")
                        return result
                elif response.status_code >= 500:
                    raise Exception(f"ANAF service error: HTTP {response.status_code}")
                elif response.status_code >= 400:
                    logger.warning(f"ANAF API returned {response.status_code} for CUI {cui}")
            
            return None
            
        except httpx.ReadError as e:
            logger.error(f"ANAF read error: {str(e)}")
            raise Exception(f"Error reading ANAF response: {str(e)}")
        except httpx.ConnectError as e:
            logger.error(f"ANAF connection error: {str(e)}")
            raise Exception(f"Cannot connect to ANAF service: {str(e)}")
        except httpx.TimeoutException as e:
            logger.error(f"ANAF timeout error: {str(e)}")
            raise Exception(f"ANAF service timeout: {str(e)}")
        except httpx.HTTPError as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"ANAF HTTP error: {error_msg}")
            raise Exception(f"ANAF HTTP error: {error_msg}")
        except ValueError as e:
            logger.error(f"Invalid CUI format: {str(e)}")
            raise Exception(f"Invalid CUI format: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get company info from ANAF: {type(e).__name__}: {str(e)}")
            raise
    
    def validate_invoice_data(self, invoice_data: InvoiceData) -> List[str]:
        """Validate invoice data for ANAF requirements"""
        errors = super().validate_invoice_data(invoice_data)
        
        # ANAF-specific validations
        if not invoice_data.supplier_tax_id:
            errors.append("Supplier tax ID (CUI) is required")
        elif not self._validate_cui_format(invoice_data.supplier_tax_id):
            errors.append("Invalid supplier tax ID format")
            
        # For B2B, customer tax ID is required
        if invoice_data.customer_country == "RO" and invoice_data.total > 5000:
            if not invoice_data.customer_tax_id or invoice_data.customer_tax_id == "-":
                errors.append("Customer tax ID is required for Romanian B2B invoices over 5000 RON")
        
        # Validate invoice number format
        if invoice_data.invoice_number and len(invoice_data.invoice_number) > 20:
            errors.append("Invoice number must not exceed 20 characters")
        
        return errors
    
    def _validate_cui_format(self, cui: str) -> bool:
        """Validate Romanian CUI format"""
        # Remove RO prefix
        cui_clean = cui.replace("RO", "").strip()
        
        # Must be numeric and 2-10 digits
        if not cui_clean.isdigit():
            return False
            
        if len(cui_clean) < 2 or len(cui_clean) > 10:
            return False
            
        return True
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid OAuth2 token"""
        if not self.access_token or (self.token_expires and datetime.now() >= self.token_expires):
            await self._authenticate()
    
    async def _authenticate(self):
        """Authenticate with ANAF OAuth2"""
        auth_url = f"{self._get_base_url()}/oauth2/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "read write"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self.token_expires = datetime.now().timestamp() + expires_in - 60  # Refresh 1 min early
            else:
                raise Exception(f"ANAF authentication failed: {response.text}")
    
    async def _upload_invoice(
        self,
        xml_content: str,
        cui: str,
        customer_cui: Optional[str] = None,
        b2c: bool = False
    ) -> Dict[str, Any]:
        """Upload invoice XML to ANAF"""
        await self._ensure_authenticated()
        
        # Determine endpoint
        endpoint = "prod/FCTEL/rest/upload"
        if b2c:
            endpoint = "prod/FCTEL/rest/uploadb2c"
        
        url = f"{self._get_base_url()}/{endpoint}"
        
        # Prepare parameters
        params = {
            "cif": cui,
            "standard": "UBL"  # Default to UBL standard
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params=params,
                content=xml_content.encode('utf-8'),
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/xml"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                # Parse XML response
                root = ET.fromstring(response.text)
                
                # Extract attributes
                attrs = root.attrib
                return {
                    "success": True,
                    "upload_index": attrs.get("index_incarcare"),
                    "response_date": attrs.get("dateResponse"),
                    "execution_status": attrs.get("ExecutionStatus"),
                    "raw_response": response.text
                }
            else:
                return {
                    "success": False,
                    "message": f"Upload failed with status {response.status_code}",
                    "details": response.text
                }
    
    async def _get_messages(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get messages from ANAF"""
        await self._ensure_authenticated()
        
        url = f"{self._get_base_url()}/prod/FCTEL/rest/listaMesajeFactura"
        params = {
            "zile": min(days, 60),  # Max 60 days
            "cif": self.config.credentials.get("company_cui", "").replace("RO", "")
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("mesaje", [])
            else:
                logger.error(f"Failed to get ANAF messages: {response.text}")
                return []
    
    async def _download_file(self, message_id: str) -> Optional[bytes]:
        """Download file from ANAF"""
        await self._ensure_authenticated()
        
        url = f"{self._get_base_url()}/prod/FCTEL/rest/descarcare"
        params = {"id": message_id}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/zip"
                }
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to download file from ANAF: {response.text}")
                return None
    
    async def _convert_xml_to_pdf(self, xml_content: bytes) -> Optional[bytes]:
        """Convert XML to PDF using ANAF service"""
        url = f"https://webservicesp.anaf.ro/prod/FCTEL/rest/transformare/FACT1/DA"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=xml_content,
                headers={"Content-Type": "application/xml"},
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to convert XML to PDF: {response.text}")
                return None
    
    def _get_base_url(self) -> str:
        """Get base URL based on environment"""
        return self.staging_url if self.use_staging else self.base_url
    
    def _map_message_to_status(self, message: Dict[str, Any]) -> InvoiceStatus:
        """Map ANAF message to invoice status"""
        message_type = message.get("tip", "").lower()
        details = message.get("detalii", "").lower()
        
        if "eroare" in message_type or "error" in details:
            return InvoiceStatus.ERROR
        elif "trimis" in details or "incarcat" in details:
            return InvoiceStatus.SENT
        elif "procesat" in details or "validat" in details:
            return InvoiceStatus.PAID
        else:
            return InvoiceStatus.PENDING