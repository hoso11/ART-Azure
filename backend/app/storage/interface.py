from abc import ABC, abstractmethod
from app.config import settings


class StorageService(ABC):
    @abstractmethod
    async def upload_file(self, bucket: str, key: str, file: bytes, content_type: str) -> str:
        """Upload a file and return its storage key."""
        ...

    @abstractmethod
    async def get_file_url(self, bucket: str, key: str) -> str:
        """Get a publicly accessible URL for the file."""
        ...

    @abstractmethod
    async def delete_file(self, bucket: str, key: str) -> None:
        """Delete a file from storage."""
        ...


def get_storage_service() -> StorageService:
    if settings.storage_backend == "azure":
        from app.storage.azure_adapter import AzureBlobStorageService
        return AzureBlobStorageService()
    else:
        from app.storage.minio_adapter import MinIOStorageService
        return MinIOStorageService()
