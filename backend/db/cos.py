"""Cloud Object Storage – production IBM COS Lite with local dev fallback."""
from __future__ import annotations
import io
import logging
import os
from functools import lru_cache
from pathlib import Path
from ..config import get_settings

logger = logging.getLogger(__name__)

LOCAL_FALLBACK_DIR = Path(__file__).resolve().parent.parent.parent / ".cos_local"


class LocalCOSStore:
    """Dev fallback – writes files to .cos_local/."""

    def __init__(self) -> None:
        LOCAL_FALLBACK_DIR.mkdir(exist_ok=True)

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = LOCAL_FALLBACK_DIR / key.replace("/", "_")
        path.write_bytes(data)
        return f"local://{path}"

    async def download(self, key: str) -> bytes:
        path = LOCAL_FALLBACK_DIR / key.replace("/", "_")
        if path.exists():
            return path.read_bytes()
        raise FileNotFoundError(key)

    async def get_url(self, key: str) -> str:
        return f"local://{LOCAL_FALLBACK_DIR / key.replace('/', '_')}"


class COSStore:
    """IBM Cloud Object Storage Lite."""

    def __init__(self, api_key: str, instance_crn: str, endpoint: str, bucket: str) -> None:
        self.bucket = bucket
        self._local = LocalCOSStore()
        try:
            import ibm_boto3  # type: ignore
            from ibm_botocore.client import Config  # type: ignore
            self._client = ibm_boto3.client(
                "s3",
                ibm_api_key_id=api_key,
                ibm_service_instance_id=instance_crn,
                config=Config(signature_version="oauth"),
                endpoint_url=endpoint,
            )
            self._available = True
        except Exception as exc:
            logger.warning("COS unavailable, using local fallback: %s", exc)
            self._client = None
            self._available = False

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        await self._local.upload(key, data, content_type)
        if not self._available:
            return await self._local.get_url(key)
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=io.BytesIO(data), ContentType=content_type)
            return f"https://{self.bucket}.{key}"
        except Exception as exc:
            logger.warning("COS upload failed: %s", exc)
            return await self._local.get_url(key)

    async def download(self, key: str) -> bytes:
        if not self._available:
            return await self._local.download(key)
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except Exception:
            return await self._local.download(key)

    async def get_url(self, key: str) -> str:
        if not self._available:
            return await self._local.get_url(key)
        return f"https://{self.bucket}.s3.cloud-object-storage.appdomain.cloud/{key}"


@lru_cache(maxsize=1)
def get_cos_store() -> COSStore:
    s = get_settings()
    return COSStore(
        api_key=s.cos_api_key,
        instance_crn=s.cos_instance_crn,
        endpoint=s.cos_endpoint,
        bucket=s.cos_bucket,
    )
