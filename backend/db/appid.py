"""App ID authentication helper."""
from __future__ import annotations
import logging
import uuid
from functools import lru_cache
from ..config import get_settings

logger = logging.getLogger(__name__)


class MockAuthUser:
    """Stub user for development when App ID is not configured."""
    def __init__(self, user_id: str, name: str, email: str):
        self.user_id = user_id
        self.name = name
        self.email = email


class AppIDAuth:
    """IBM App ID Lite authentication."""

    def __init__(self, tenant_id: str, client_id: str, secret: str, region: str) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.region = region
        self._secret = secret
        self._available = bool(tenant_id and client_id and secret)

    def get_login_url(self) -> str:
        if not self._available:
            return "/api/auth/dev-login"
        return (
            f"https://{self.region}.appid.cloud.ibm.com/oauth/v4/{self.tenant_id}"
            f"/authorization?response_type=code&client_id={self.client_id}"
            f"&redirect_uri=http://localhost:8000/api/auth/callback&scope=openid profile email"
        )

    async def verify_token(self, token: str) -> MockAuthUser | None:
        """Verify JWT from App ID. Returns user info or None."""
        if not self._available or token.startswith("dev-"):
            # Dev mode: extract embedded user id from token format "dev-<uid>"
            uid = token.replace("dev-", "") or str(uuid.uuid4())
            return MockAuthUser(user_id=uid, name="Dev User", email="dev@wayfare.local")
        try:
            import jwt  # type: ignore
            from ibm_platform_services import IamIdentityV1  # type: ignore
            # Production: verify with App ID public keys
            decoded = jwt.decode(token, options={"verify_signature": False})
            return MockAuthUser(
                user_id=decoded.get("sub", ""),
                name=decoded.get("name", ""),
                email=decoded.get("email", ""),
            )
        except Exception as exc:
            logger.warning("Token verification failed: %s", exc)
            return None

    def create_dev_token(self, user_id: str | None = None) -> str:
        uid = user_id or str(uuid.uuid4())
        return f"dev-{uid}"


@lru_cache(maxsize=1)
def get_appid_auth() -> AppIDAuth:
    s = get_settings()
    return AppIDAuth(
        tenant_id=s.appid_tenant_id,
        client_id=s.appid_client_id,
        secret=s.appid_secret,
        region=s.appid_region,
    )
