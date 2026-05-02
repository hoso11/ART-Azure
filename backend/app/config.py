from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import Optional


# Known weak / placeholder values that must never be used as the JWT signing
# key in production. Anyone with one of these can mint admin tokens.
WEAK_SECRET_KEYS = frozenset({
    "",
    "change-me",
    "changeme",
    "secret",
    "placeholder",
    "placeholder-dev-secret-change-me",
    "your-secret-key",
    "your-secret-key-here",
})


class Settings(BaseSettings):
    # General
    app_name: str = "ART Manufacturing"
    app_env: str = "development"
    debug: bool = True
    log_format: str = "pretty"  # "pretty" or "json"

    # Security
    secret_key: str = "change-me"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    allowed_origins: str = "http://localhost,http://localhost:3000"

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        # Only enforced in production. Local dev / docker-compose / pytest can
        # keep using the default "change-me" so the existing dev workflow is
        # untouched.
        if self.app_env != "production":
            return self
        if self.secret_key in WEAK_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY is a known placeholder; refuse to start in production. "
                "Generate a real key with `openssl rand -hex 32` and set it via "
                "Terraform `backend_secret_key` (gitignored terraform.tfvars)."
            )
        if len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters in production "
                "(got {n}).".format(n=len(self.secret_key))
            )
        return self

    # Database
    database_url: str = "postgresql+asyncpg://art_user:art_password@postgres:5432/art_manufacturing"
    database_url_sync: str = "postgresql://art_user:art_password@postgres:5432/art_manufacturing"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Storage
    storage_backend: str = "minio"  # "minio" or "azure"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "art-images"
    minio_use_ssl: bool = False
    minio_external_endpoint: str = "localhost:9000"

    # Azure Blob (when storage_backend=azure)
    # Two auth paths, selected at runtime by AzureBlobStorageService:
    #   1. Managed Identity (preferred): set azure_storage_account_url to the
    #      account's primary blob endpoint (https://<acct>.blob.core.windows.net/).
    #      The adapter authenticates via DefaultAzureCredential, which on Azure
    #      App Service resolves to the Web App's System-Assigned identity.
    #      Requires the identity to hold "Storage Blob Data Contributor" on
    #      the account scope (Terraform provisions this).
    #   2. Connection string (fallback): leave azure_storage_account_url unset
    #      and provide azure_storage_connection_string. Used in local dev or
    #      as a break-glass while MI propagates after a fresh deploy.
    azure_storage_account_url: Optional[str] = None
    azure_storage_connection_string: Optional[str] = None
    azure_storage_container: str = "art-images"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@art-manufacturing.com"
    smtp_use_tls: bool = False

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # Sentry
    sentry_dsn: Optional[str] = None

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
