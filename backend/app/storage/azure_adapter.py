"""
Azure Blob Storage adapter.

To enable:
1. pip install azure-storage-blob
2. Set STORAGE_BACKEND=azure in environment
3. Set AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER

Implementation:

from azure.storage.blob import BlobServiceClient
from app.config import settings
from app.storage.interface import StorageService


class AzureBlobStorageService(StorageService):
    def __init__(self):
        self.client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        self.container = settings.azure_storage_container
        self._ensure_container()

    def _ensure_container(self):
        try:
            self.client.create_container(self.container)
        except Exception:
            pass  # Container already exists

    async def upload_file(self, bucket: str, key: str, file: bytes, content_type: str) -> str:
        blob_client = self.client.get_blob_client(
            container=self.container, blob=key
        )
        blob_client.upload_blob(
            file, overwrite=True, content_settings={"content_type": content_type}
        )
        return key

    async def get_file_url(self, bucket: str, key: str) -> str:
        blob_client = self.client.get_blob_client(
            container=self.container, blob=key
        )
        return blob_client.url

    async def delete_file(self, bucket: str, key: str) -> None:
        blob_client = self.client.get_blob_client(
            container=self.container, blob=key
        )
        blob_client.delete_blob()
"""

# Placeholder — uncomment and install azure-storage-blob when deploying to Azure
raise ImportError(
    "Azure Blob Storage adapter is a placeholder. "
    "Install azure-storage-blob and uncomment the implementation above."
)
