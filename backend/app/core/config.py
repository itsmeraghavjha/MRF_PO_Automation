from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./storage/heritage_po.db"

    # Email
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""
    IMAP_FOLDER: str = "INBOX"
    IMAP_POLL_INTERVAL_SECONDS: int = 60

    # AI
    LLM_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BACKOFF_SECONDS: int = 5

    # SAP
    SAP_OUTPUT_FOLDER: str = "./storage/sap_output"

    # App
    APP_SECRET_KEY: str = "change-me"
    APP_BASE_URL: str = "http://localhost:8000"   # ← Phase 3: used in vendor portal email links
    PDF_STORAGE_DIR: str = "./storage/pdfs"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Validation Rules
    RULE_VR01_PRODUCT_MAPPING: bool = True
    RULE_VR02_PRICE_VALIDATION: bool = True
    RULE_VR03_INVENTORY_CHECK: bool = True
    RULE_VR04_CASE_LOT: bool = True
    RULE_VR05_LOCATION_MAPPING: bool = True
    RULE_VR06_GSTIN: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()