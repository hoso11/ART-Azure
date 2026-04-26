import io
import json
from minio import Minio
from loguru import logger
from app.config import settings
from app.storage.interface import StorageService


class MinIOStorageService(StorageService):
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
        self._ensure_bucket(settings.minio_bucket)

    def _ensure_bucket(self, bucket: str):
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            logger.info(f"Created MinIO bucket: {bucket}")
        self._set_public_read_policy(bucket)

    def _set_public_read_policy(self, bucket: str):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
        try:
            self.client.set_bucket_policy(bucket, json.dumps(policy))
            logger.info(f"Set public-read policy on bucket: {bucket}")
        except Exception as e:
            logger.warning(f"Could not set bucket policy: {e}")

    async def upload_file(self, bucket: str, key: str, file: bytes, content_type: str) -> str:
        self._ensure_bucket(bucket)
        self.client.put_object(
            bucket,
            key,
            io.BytesIO(file),
            length=len(file),
            content_type=content_type,
        )
        logger.info("storage.upload", bucket=bucket, key=key, size=len(file))
        return key

    async def get_file_url(self, bucket: str, key: str) -> str:
        protocol = "https" if settings.minio_use_ssl else "http"
        return f"{protocol}://{settings.minio_external_endpoint}/{bucket}/{key}"

    async def delete_file(self, bucket: str, key: str) -> None:
        self.client.remove_object(bucket, key)
        logger.info("storage.delete", bucket=bucket, key=key)
