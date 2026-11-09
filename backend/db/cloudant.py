"""Cloudant store – production IBM Cloudant Lite with in-memory dev fallback."""
from __future__ import annotations
import logging
from typing import Any
from functools import lru_cache
from ..config import get_settings

logger = logging.getLogger(__name__)


class InMemoryStore:
    """Dev fallback – same interface as Cloudant."""

    def __init__(self) -> None:
        self._dbs: dict[str, dict[str, Any]] = {}

    async def get(self, db: str, doc_id: str) -> dict | None:
        return self._dbs.get(db, {}).get(doc_id)

    async def put(self, db: str, doc_id: str, doc: dict) -> None:
        self._dbs.setdefault(db, {})[doc_id] = doc

    async def delete(self, db: str, doc_id: str) -> None:
        self._dbs.get(db, {}).pop(doc_id, None)

    async def query(self, db: str, selector: dict) -> list[dict]:
        docs = self._dbs.get(db, {})
        results = []
        for doc in docs.values():
            match = all(doc.get(k) == v for k, v in selector.items())
            if match:
                results.append(doc)
        return results


class CloudantStore:
    """IBM Cloudant Lite store."""

    def __init__(self, url: str, api_key: str) -> None:
        try:
            from ibmcloudant.cloudant_v1 import CloudantV1
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
            auth = IAMAuthenticator(api_key)
            self._client = CloudantV1(authenticator=auth)
            self._client.set_service_url(url)
            self._available = True
        except Exception as exc:
            logger.warning("Cloudant unavailable, using in-memory store: %s", exc)
            self._client = None
            self._available = False
        self._mem = InMemoryStore()

    async def get(self, db: str, doc_id: str) -> dict | None:
        if not self._available:
            return await self._mem.get(db, doc_id)
        try:
            resp = self._client.get_document(db=db, doc_id=doc_id).get_result()
            return resp
        except Exception:
            return await self._mem.get(db, doc_id)

    async def put(self, db: str, doc_id: str, doc: dict) -> None:
        await self._mem.put(db, doc_id, doc)
        if not self._available:
            return
        try:
            from ibmcloudant.cloudant_v1 import Document
            doc["_id"] = doc_id
            existing = await self.get(db, doc_id)
            if existing and "_rev" in existing:
                doc["_rev"] = existing["_rev"]
            d = Document(**doc)
            self._client.put_document(db=db, doc_id=doc_id, document=d)
        except Exception as exc:
            logger.warning("Cloudant put failed: %s", exc)

    async def delete(self, db: str, doc_id: str) -> None:
        await self._mem.delete(db, doc_id)
        if not self._available:
            return
        try:
            existing = await self.get(db, doc_id)
            if existing and "_rev" in existing:
                self._client.delete_document(db=db, doc_id=doc_id, rev=existing["_rev"])
        except Exception as exc:
            logger.warning("Cloudant delete failed: %s", exc)

    async def query(self, db: str, selector: dict) -> list[dict]:
        if not self._available:
            return await self._mem.query(db, selector)
        try:
            from ibmcloudant.cloudant_v1 import PostFindEnums
            resp = self._client.post_find(db=db, selector=selector).get_result()
            return resp.get("docs", [])
        except Exception:
            return await self._mem.query(db, selector)


@lru_cache(maxsize=1)
def get_cloudant_store() -> CloudantStore:
    s = get_settings()
    return CloudantStore(url=s.cloudant_url, api_key=s.cloudant_api_key)
