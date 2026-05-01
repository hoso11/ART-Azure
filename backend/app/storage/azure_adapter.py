"""Azure Blob Storage adapter.

Active when STORAGE_BACKEND=azure. Connection string and container name are
injected via Azure App Settings (AZURE_STORAGE_CONNECTION_STRING,
AZURE_STORAGE_CONTAINER) — Terraform wires both from the storage account
resource. Container is private; image bytes reach the browser via the
backend proxy at /api/v1/products/images/file/{key}, never directly.
"""

from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from loguru import logger

from app.config import settings
from app.storage.interface import StorageService


class AzureBlobStorageService(StorageService):
    def __init__(self):
        self.client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        self.bucket = settings.azure_storage_container
        self._ensure_container(self.bucket)

    def _ensure_container(self, container: str) -> None:
        try:
            self.client.create_container(container)
            logger.info(f"Created Azure Blob container: {container}")
        except ResourceExistsError:
            pass

    def _blob(self, container: str, key: str):
        return self.client.get_blob_client(container=container, blob=key)

    async def upload_file(self, bucket: str, key: str, file: bytes, content_type: str) -> str:
        self._blob(bucket, key).upload_blob(
            file,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        logger.info("storage.upload", bucket=bucket, key=key, size=len(file))
        return key

    async def download_file(self, bucket: str, key: str) -> tuple[bytes, str]:
        blob = self._blob(bucket, key)
        try:
            stream = blob.download_blob()
            data = stream.readall()
            props = stream.properties
            content_type = (
                props.content_settings.content_type
                if props and props.content_settings
                else "application/octet-stream"
            )
        except ResourceNotFoundError:
            raise FileNotFoundError(f"blob not found: {bucket}/{key}")
        return data, content_type

    async def get_file_url(self, bucket: str, key: str) -> str:
        # Container is private — this URL is not browser-fetchable. The
        # router populates response.url with /api/v1/products/images/file/{key}
        # which goes through the backend proxy. This method is kept for
        # interface parity and admin-side debugging.
        return self._blob(bucket, key).url

    async def delete_file(self, bucket: str, key: str) -> None:
        try:
            self._blob(bucket, key).delete_blob()
        except ResourceNotFoundError:
            pass
        logger.info("storage.delete", bucket=bucket, key=key)
