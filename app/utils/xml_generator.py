"""
XML generator for ANAF e-Factura (UBL 2.1 format)
"""
from lxml import etree
from datetime import datetime
from typing import Dict, Any
from app.core.provider_interface import InvoiceData


class ANAFXMLGenerator:
    """Generate UBL 2.1 compliant XML for Romanian e-Invoices"""
    
    def __init__(self):
        self.nsmap = {
            None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }
    
    def generate_invoice_xml(self, invoice_data: InvoiceData) -> str:
        """Generate complete invoice XML"""
        root = etree.Element("Invoice", nsmap=self.nsmap)
        
        # Add UBL version and customization
        self._add_header(root, invoice_data)
        
        # Add invoice details
        self._add_invoice_details(root, invoice_data)
        
        # Add supplier (AccountingSupplierParty)
        self._add_supplier_party(root, invoice_data)
        
        # Add customer (AccountingCustomerParty)
        self._add_customer_party(root, invoice_data)
        
        # Add payment means
        self._add_payment_means(root, invoice_data)
        
        # Add tax totals
        self._add_tax_total(root, invoice_data)
        
        # Add monetary totals
        self._add_legal_monetary_total(root, invoice_data)
        
        # Add invoice lines
        self._add_invoice_lines(root, invoice_data)
        
        # Return formatted XML
        return etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        ).decode("utf-8")
    
    def _add_header(self, root: etree.Element, invoice_data: InvoiceData):
        """Add UBL header elements"""
        cbc = "{%s}" % self.nsmap["cbc"]
        
        # UBL Version
        etree.SubElement(root, f"{cbc}UBLVersionID").text = "2.1"
        
        # Customization ID for Romanian e-Invoice
        etree.SubElement(root, f"{cbc}CustomizationID").text = "urn:cen.eu:en16931:2017#compliant#urn:efactura.mfinante.ro:CIUS-RO:1.3.0"
        
        # Profile ID
        etree.SubElement(root, f"{cbc}ProfileID").text = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
    
    def _add_invoice_details(self, root: etree.Element, invoice_data: InvoiceData):
        """Add basic invoice details"""
        cbc = "{%s}" % self.nsmap["cbc"]
        
        # Invoice ID/Number
        invoice_number = invoice_data.invoice_number or f"AUTO-{invoice_data.source_id[:8]}"
        etree.SubElement(root, f"{cbc}ID").text = invoice_number
        
        # Issue date
        etree.SubElement(root, f"{cbc}IssueDate").text = invoice_data.invoice_date.strftime("%Y-%m-%d")
        
        # Due date
        if invoice_data.due_date:
            etree.SubElement(root, f"{cbc}DueDate").text = invoice_data.due_date.strftime("%Y-%m-%d")
        
        # Invoice type code (380 = Commercial invoice)
        etree.SubElement(root, f"{cbc}InvoiceTypeCode").text = "380"
        
        # Currency
        etree.SubElement(root, f"{cbc}DocumentCurrencyCode").text = invoice_data.currency
        
        # Accounting cost (optional)
        if invoice_data.metadata.get("accounting_cost"):
            etree.SubElement(root, f"{cbc}AccountingCost").text = invoice_data.metadata["accounting_cost"]
    
    def _add_supplier_party(self, root: etree.Element, invoice_data: InvoiceData):
        """Add supplier (seller) information"""
        cac = "{%s}" % self.nsmap["cac"]
        cbc = "{%s}" % self.nsmap["cbc"]
        
        supplier_party = etree.SubElement(root, f"{cac}AccountingSupplierParty")
        party = etree.SubElement(supplier_party, f"{cac}Party")
        
        # Party identification (CUI)
        party_id = etree.SubElement(party, f"{cac}PartyIdentification")
        etree.SubElement(party_id, f"{cbc}ID").text = invoice_data.supplier_tax_id
        
        # Party name
        party_name = etree.SubElement(party, f"{cac}PartyName")
        etree.SubElement(party_name, f"{cbc}Name").text = invoice_data.supplier_name
        
        # Postal address
        address = etree.SubElement(party, f"{cac}PostalAddress")
        etree.SubElement(address, f"{cbc}StreetName").text = invoice_data.supplier_address.get("street", "")
        etree.SubElement(address, f"{cbc}CityName").text = invoice_data.supplier_address.get("city", "")
        etree.SubElement(address, f"{cbc}PostalZone").text = invoice_data.supplier_address.get("postal_code", "")
        
        country = etree.SubElement(address, f"{cac}Country")
        etree.SubElement(country, f"{cbc}IdentificationCode").text = "RO"
        
        # Tax scheme
        party_tax = etree.SubElement(party, f"{cac}PartyTaxScheme")
        etree.SubElement(party_tax, f"{cbc}CompanyID").text = invoice_data.supplier_tax_id
        tax_scheme = etree.SubElement(party_tax, f"{cac}TaxScheme")
        etree.SubElement(tax_scheme, f"{cbc}ID").text = "VAT"
        
        # Legal entity
        legal_entity = etree.SubElement(party, f"{cac}PartyLegalEntity")
        etree.SubElement(legal_entity, f"{cbc}RegistrationName").text = invoice_data.supplier_name
        if invoice_data.supplier_registration:
            etree.SubElement(legal_entity, f"{cbc}CompanyID").text = invoice_data.supplier_registration
    
    def _add_customer_party(self, root: etree.Element, invoice_data: InvoiceData):
        """Add customer (buyer) information"""
        cac = "{%s}" % self.nsmap["cac"]
        cbc = "{%s}" % self.nsmap["cbc"]
        
        customer_party = etree.SubElement(root, f"{cac}AccountingCustomerParty")
        party = etree.SubElement(customer_party, f"{cac}Party")
        
        # Party identification
        if invoice_data.customer_tax_id and invoice_data.customer_tax_id != "-":
            party_id = etree.SubElement(party, f"{cac}PartyIdentification")
            etree.SubElement(party_id, f"{cbc}ID").text = invoice_data.customer_tax_id
        
        # Party name
        party_name = etree.SubElement(party, f"{cac}PartyName")
        etree.SubElement(party_name, f"{cbc}Name").text = invoice_data.customer_name
        
        # Postal address
        address = etree.SubElement(party, f"{cac}PostalAddress")
        if invoice_data.customer_address:
            street = invoice_data.customer_address.get("line1", "")
            if invoice_data.customer_address.get("line2"):
                street += f", {invoice_data.customer_address['line2']}"
            etree.SubElement(address, f"{cbc}StreetName").text = street
            etree.SubElement(address, f"{cbc}CityName").text = invoice_data.customer_address.get("city", "N/A")
            etree.SubElement(address, f"{cbc}PostalZone").text = invoice_data.customer_address.get("postal_code", "")
        else:
            etree.SubElement(address, f"{cbc}StreetName").text = "N/A"
            etree.SubElement(address, f"{cbc}CityName").text = "N/A"
        
        country = etree.SubElement(address, f"{cac}Country")
        etree.SubElement(country, f"{cbc}IdentificationCode").text = invoice_data.customer_country
        
        # Tax scheme (if applicable)
        if invoice_data.customer_tax_id and invoice_data.customer_tax_id != "-":
            party_tax = etree.SubElement(party, f"{cac}PartyTaxScheme")
            etree.SubElement(party_tax, f"{cbc}CompanyID").text = invoice_data.customer_tax_id
            tax_scheme = etree.SubElement(party_tax, f"{cac}TaxScheme")
            etree.SubElement(tax_scheme, f"{cbc}ID").text = "VAT"
        
        # Legal entity
        legal_entity = etree.SubElement(party, f"{cac}PartyLegalEntity")
        etree.SubElement(legal_entity, f"{cbc}RegistrationName").text = invoice_data.customer_name
        
        # Contact (email)
        if invoice_data.customer_email:
            contact = etree.SubElement(party, f"{cac}Contact")
            etree.SubElement(contact, f"{cbc}ElectronicMail").text = invoice_data.customer_email
    
    def _add_payment_means(self, root: etree.Element, invoice_data: InvoiceData):
        """Add payment means information"""
        cac = "{%s}" % self.nsmap["cac"]
        cbc = "{%s}" % self.nsmap["cbc"]
        
        payment_means = etree.SubElement(root, f"{cac}PaymentMeans")
        # 42 = Payment to bank account
        etree.SubElement(payment_means, f"{cbc}PaymentMeansCode").text = "42"
        
        if invoice_data.metadata.get("payment_id"):
            etree.SubElement(payment_means, f"{cbc}PaymentID").text = invoice_data.metadata["payment_id"]
    
    def _add_tax_total(self, root: etree.Element, invoice_data: InvoiceData):
        """Add tax total information"""
        cac = "{%s}" % self.nsmap["cac"]
        cbc = "{%s}" % self.nsmap["cbc"]
        
        tax_total = etree.SubElement(root, f"{cac}TaxTotal")
        
        # Total tax amount
        tax_amount = etree.SubElement(tax_total, f"{cbc}TaxAmount")
        tax_amount.set("currencyID", invoice_data.currency)
        tax_amount.text = f"{invoice_data.tax_amount:.2f}"
        
        # Tax subtotal (by rate)
        tax_rates = {}
        for line in invoice_data.lines:
            rate = line.get("tax_rate", 19.0)
            if rate not in tax_rates:
                tax_rates[rate] = {"taxable": 0, "tax": 0}
            
            line_amount = float(line["amount"])
            line_tax = line_amount * (rate / 100)
            
            tax_rates[rate]["taxable"] += line_amount
            tax_rates[rate]["tax"] += line_tax
        
        for rate, amounts in tax_rates.items():
            tax_subtotal = etree.SubElement(tax_total, f"{cac}TaxSubtotal")
            
            # Taxable amount
            taxable_amount = etree.SubElement(tax_subtotal, f"{cbc}TaxableAmount")
            taxable_amount.set("currencyID", invoice_data.currency)
            taxable_amount.text = f"{amounts['taxable']:.2f}"
            
            # Tax amount
            subtotal_tax_amount = etree.SubElement(tax_subtotal, f"{cbc}TaxAmount")
            subtotal_tax_amount.set("currencyID", invoice_data.currency)
            subtotal_tax_amount.text = f"{amounts['tax']:.2f}"
            
            # Tax category
            tax_category = etree.SubElement(tax_subtotal, f"{cac}TaxCategory")
            etree.SubElement(tax_category, f"{cbc}ID").text = "S"  # Standard rate
            etree.SubElement(tax_category, f"{cbc}Percent").text = f"{rate:.2f}"
            
            tax_scheme = etree.SubElement(tax_category, f"{cac}TaxScheme")
            etree.SubElement(tax_scheme, f"{cbc}ID").text = "VAT"
    
    def _add_legal_monetary_total(self, root: etree.Element, invoice_data: InvoiceData):
        """Add monetary totals"""
        cac = "{%s}" % self.nsmap["cac"]
        cbc = "{%s}" % self.nsmap["cbc"]
        
        monetary_total = etree.SubElement(root, f"{cac}LegalMonetaryTotal")
        
        # Line extension amount (sum of line amounts excluding tax)
        line_extension = etree.SubElement(monetary_total, f"{cbc}LineExtensionAmount")
        line_extension.set("currencyID", invoice_data.currency)
        line_extension.text = f"{invoice_data.subtotal:.2f}"
        
        # Tax exclusive amount
        tax_exclusive = etree.SubElement(monetary_total, f"{cbc}TaxExclusiveAmount")
        tax_exclusive.set("currencyID", invoice_data.currency)
        tax_exclusive.text = f"{invoice_data.subtotal:.2f}"
        
        # Tax inclusive amount
        tax_inclusive = etree.SubElement(monetary_total, f"{cbc}TaxInclusiveAmount")
        tax_inclusive.set("currencyID", invoice_data.currency)
        tax_inclusive.text = f"{invoice_data.total:.2f}"
        
        # Payable amount
        payable = etree.SubElement(monetary_total, f"{cbc}PayableAmount")
        payable.set("currencyID", invoice_data.currency)
        payable.text = f"{invoice_data.total:.2f}"
    
    def _add_invoice_lines(self, root: etree.Element, invoice_data: InvoiceData):
        """Add invoice line items"""
        cac = "{%s}" % self.nsmap["cac"]
        cbc = "{%s}" % self.nsmap["cbc"]
        
        for idx, line in enumerate(invoice_data.lines, 1):
            invoice_line = etree.SubElement(root, f"{cac}InvoiceLine")
            
            # Line ID
            etree.SubElement(invoice_line, f"{cbc}ID").text = str(idx)
            
            # Quantity
            quantity = etree.SubElement(invoice_line, f"{cbc}InvoicedQuantity")
            quantity.set("unitCode", line.get("unit_code", "C62"))  # C62 = piece
            quantity.text = str(line["quantity"])
            
            # Line amount
            line_amount = etree.SubElement(invoice_line, f"{cbc}LineExtensionAmount")
            line_amount.set("currencyID", invoice_data.currency)
            line_amount.text = f"{line['amount']:.2f}"
            
            # Item
            item = etree.SubElement(invoice_line, f"{cac}Item")
            etree.SubElement(item, f"{cbc}Description").text = line["description"]
            
            # Item name
            etree.SubElement(item, f"{cbc}Name").text = line["description"][:100]  # Max 100 chars
            
            # Classified tax category
            tax_category = etree.SubElement(item, f"{cac}ClassifiedTaxCategory")
            etree.SubElement(tax_category, f"{cbc}ID").text = "S"
            etree.SubElement(tax_category, f"{cbc}Percent").text = f"{line.get('tax_rate', 19.0):.2f}"
            tax_scheme = etree.SubElement(tax_category, f"{cac}TaxScheme")
            etree.SubElement(tax_scheme, f"{cbc}ID").text = "VAT"
            
            # Price
            price = etree.SubElement(invoice_line, f"{cac}Price")
            price_amount = etree.SubElement(price, f"{cbc}PriceAmount")
            price_amount.set("currencyID", invoice_data.currency)
            price_amount.text = f"{line['unit_price']:.2f}"