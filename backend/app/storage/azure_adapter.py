"""Azure Blob Storage adapter.

Active when STORAGE_BACKEND=azure. Two auth paths, selected at __init__:

  1. Managed Identity (preferred). When AZURE_STORAGE_ACCOUNT_URL is set the
     adapter constructs BlobServiceClient(account_url, DefaultAzureCredential()).
     On Azure App Service DefaultAzureCredential resolves to the Web App's
     System-Assigned identity, which Terraform grants "Storage Blob Data
     Contributor" on the storage account scope. No shared keys leave the
     control plane this way.

  2. Connection string (fallback). When AZURE_STORAGE_ACCOUNT_URL is unset
     and AZURE_STORAGE_CONNECTION_STRING is provided, the adapter falls back
     to BlobServiceClient.from_connection_string. Used in local dev and as a
     break-glass while a fresh deploy waits on MI role-assignment propagation.

Container is private; image bytes reach the browser via the backend proxy at
/api/v1/products/images/file/{key}, never directly.
"""

from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from loguru import logger

from app.config import settings
from app.storage.interface import StorageService


class AzureBlobStorageService(StorageService):
    def __init__(self):
        if settings.azure_storage_account_url:
            self.client = BlobServiceClient(
                account_url=settings.azure_storage_account_url,
                credential=DefaultAzureCredential(),
            )
            self._auth_mode = "managed_identity"
        elif settings.azure_storage_connection_string:
            self.client = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
            self._auth_mode = "connection_string"
        else:
            raise RuntimeError(
                "Azure storage requires either AZURE_STORAGE_ACCOUNT_URL "
                "(Managed Identity) or AZURE_STORAGE_CONNECTION_STRING. "
                "Neither is set."
            )
        logger.info("storage.azure.init", auth_mode=self._auth_mode)
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
