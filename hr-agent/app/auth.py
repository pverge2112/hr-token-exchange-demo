"""Authentication and token handling utilities."""
from typing import Optional
from fastapi import Header, HTTPException, status
import base64
import json
import logging

logger = logging.getLogger(__name__)


class TokenContext:
    """Context object holding authentication information from headers."""

    def __init__(
        self,
        user_scopes: Optional[str] = None,
        user_sub: Optional[str] = None,
        actor_chain: Optional[str] = None,
        authorization: Optional[str] = None,
        x_introspection_token: Optional[str] = None,
    ):
        self.user_scopes = user_scopes or ""
        self.user_sub = user_sub or ""
        self.actor_chain = actor_chain or ""
        self.authorization = authorization or ""
        self.x_introspection_token = x_introspection_token or ""

        # Extract the actual exchanged token from x-introspection-token header
        self.exchanged_token = self._extract_exchanged_token()

        # Parse scopes into a list
        self.scopes_list = [s.strip() for s in self.user_scopes.split() if s.strip()]

    def _extract_exchanged_token(self) -> Optional[str]:
        """Extract the actual JWT token from Kong's x-introspection-token header.

        Kong base64-encodes the RFC 8693 token exchange JSON response and sends it
        in the x-introspection-token header. We need to decode and extract access_token.
        """
        if not self.x_introspection_token:
            return None

        try:
            # Base64 decode the header value
            decoded_bytes = base64.b64decode(self.x_introspection_token)
            decoded_json = json.loads(decoded_bytes)

            # Extract the access_token from the RFC 8693 response
            access_token = decoded_json.get("access_token")
            if access_token:
                logger.info("[TOKEN] Successfully extracted exchanged token from x-introspection-token header")
                return access_token
            else:
                logger.warning("[TOKEN] x-introspection-token decoded but no access_token found")
                return None
        except Exception as e:
            logger.error(f"[TOKEN] Failed to extract exchanged token from x-introspection-token: {e}")
            return None

    def has_scope(self, scope: str) -> bool:
        """Check if a specific scope is available."""
        return scope in self.scopes_list

    def get_headers(self, include_auth: bool = True) -> dict:
        """
        Get headers to propagate to downstream services.

        Args:
            include_auth: Whether to include Authorization header.
                         Set to False for LLM API calls since Kong AI Proxy handles auth.
        """
        headers = {
            "X-User-Scopes": self.user_scopes,
            "X-User-Sub": self.user_sub,
            "X-Actor-Chain": self.actor_chain,
        }
        if include_auth and self.authorization:
            headers["Authorization"] = self.authorization
        return headers


async def get_token_context(
    x_user_scopes: Optional[str] = Header(None, alias="X-User-Scopes"),
    x_user_sub: Optional[str] = Header(None, alias="X-User-Sub"),
    x_actor_chain: Optional[str] = Header(None, alias="X-Actor-Chain"),
    authorization: Optional[str] = Header(None),
    x_introspection_token: Optional[str] = Header(None, alias="x-introspection-token"),
) -> TokenContext:
    """
    FastAPI dependency to extract token context from headers.

    These headers are injected by Kong Gateway after token exchange.
    The x-introspection-token header contains the RFC 8693 token exchange response
    (base64-encoded) with the actual exchanged JWT token.
    """
    return TokenContext(
        user_scopes=x_user_scopes,
        user_sub=x_user_sub,
        actor_chain=x_actor_chain,
        authorization=authorization,
        x_introspection_token=x_introspection_token,
    )
