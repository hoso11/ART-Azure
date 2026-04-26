from pydantic_settings import BaseSettings
from typing import Optional


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
