"""
Application configuration settings
"""
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # API Configuration
    api_title: str = "Stripe Invoice Sync API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000"]
    
    # Stripe Configuration
    stripe_api_key: str = Field(..., env="STRIPE_API_KEY")
    stripe_webhook_secret: Optional[str] = Field(None, env="STRIPE_WEBHOOK_SECRET")
    
    # Company Information (Your company as supplier)
    company_name: str = Field(..., env="COMPANY_NAME")
    company_cui: str = Field(..., env="COMPANY_CUI")
    company_address_street: str = Field(..., env="COMPANY_ADDRESS_STREET")
    company_address_city: str = Field(..., env="COMPANY_ADDRESS_CITY")
    company_address_county: Optional[str] = Field(None, env="COMPANY_ADDRESS_COUNTY")
    company_address_country: str = Field("RO", env="COMPANY_ADDRESS_COUNTRY")
    company_address_postal: str = Field(..., env="COMPANY_ADDRESS_POSTAL")
    company_registration: Optional[str] = Field(None, env="COMPANY_REGISTRATION")
    
    # Default Invoice Settings
    default_invoice_series: str = Field("FACT", env="DEFAULT_INVOICE_SERIES")
    default_tax_rate: float = Field(19.0, env="DEFAULT_TAX_RATE")
    default_currency: str = Field("RON", env="DEFAULT_CURRENCY")
    default_payment_days: int = Field(30, env="DEFAULT_PAYMENT_DAYS")
    stripe_prices_include_tax: bool = Field(True, env="STRIPE_PRICES_INCLUDE_TAX")
    
    # Provider Configurations
    # ANAF
    anaf_enabled: bool = Field(True, env="ANAF_ENABLED")
    anaf_client_id: Optional[str] = Field(None, env="ANAF_CLIENT_ID")
    anaf_client_secret: Optional[str] = Field(None, env="ANAF_CLIENT_SECRET")
    anaf_use_staging: bool = Field(False, env="ANAF_USE_STAGING")
    
    # SmartBill
    smartbill_enabled: bool = Field(False, env="SMARTBILL_ENABLED")
    smartbill_username: Optional[str] = Field(None, env="SMARTBILL_USERNAME")
    smartbill_token: Optional[str] = Field(None, env="SMARTBILL_TOKEN")
    smartbill_send_email: bool = Field(True, env="SMARTBILL_SEND_EMAIL")
    
    # Database
    database_url: str = Field("sqlite:///./stripe_invoice_sync.db", env="DATABASE_URL")
    
    # Processing Options
    auto_process_invoices: bool = Field(False, env="AUTO_PROCESS_INVOICES")
    batch_size: int = Field(10, env="BATCH_SIZE")
    rate_limit_per_second: int = Field(3, env="RATE_LIMIT_PER_SECOND")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator("company_cui")
    def validate_cui(cls, v):
        """Ensure CUI has RO prefix"""
        if not v.startswith("RO"):
            return f"RO{v}"
        return v
    
    def get_supplier_info(self) -> Dict[str, Any]:
        """Get supplier information dictionary"""
        return {
            "name": self.company_name,
            "tax_id": self.company_cui,
            "address": {
                "street": self.company_address_street,
                "city": self.company_address_city,
                "county": self.company_address_county,
                "postal_code": self.company_address_postal,
                "country": self.company_address_country
            },
            "registration": self.company_registration,
            "default_tax_rate": self.default_tax_rate
        }
    
    def get_anaf_config(self) -> Dict[str, Any]:
        """Get ANAF provider configuration"""
        return {
            "name": "anaf",
            "enabled": self.anaf_enabled,
            "auth_type": "oauth2",
            "credentials": {
                "client_id": self.anaf_client_id,
                "client_secret": self.anaf_client_secret,
                "company_cui": self.company_cui.replace("RO", "")
            },
            "options": {
                "use_staging": self.anaf_use_staging,
                "require_tax_id": True
            }
        }
    
    def get_smartbill_config(self) -> Dict[str, Any]:
        """Get SmartBill provider configuration"""
        return {
            "name": "smartbill",
            "enabled": self.smartbill_enabled,
            "auth_type": "api_key",
            "credentials": {
                "username": self.smartbill_username,
                "token": self.smartbill_token,
                "company_cif": self.company_cui
            },
            "options": {
                "invoice_series": self.default_invoice_series,
                "send_email": self.smartbill_send_email,
                "require_tax_id": False
            }
        }


# Create settings instance
settings = Settings()