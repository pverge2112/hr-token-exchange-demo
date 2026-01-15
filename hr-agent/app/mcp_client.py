"""MCP (Model Context Protocol) client for calling HR MCP Server tools."""
import httpx
import logging
from typing import Any, Dict, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for interacting with the HR MCP Server."""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize MCP client."""
        self.base_url = base_url or settings.mcp_server_url
        self.request_id = 0
        self.last_mcp_token = None  # Store the last captured MCP token

    def _next_id(self) -> int:
        """Generate next request ID."""
        self.request_id += 1
        return self.request_id

    async def initialize(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Initialize MCP session.

        Args:
            headers: Optional headers to include (for auth/scopes)

        Returns:
            Server capabilities and info
        """
        # Ensure Accept header is set for Kong AI MCP Proxy compatibility
        request_headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json={
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "initialize",
                    "params": {"capabilities": {}},
                },
                headers=request_headers,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(f"MCP initialize error: {result['error']}")

            return result.get("result", {})

    async def list_tools(self, headers: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        List available MCP tools (filtered by scopes if headers provided).

        Args:
            headers: Optional headers including X-User-Scopes for filtering

        Returns:
            List of available tools
        """
        # Ensure Accept header is set for Kong AI MCP Proxy compatibility
        request_headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json={
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "tools/list",
                    "params": {},
                },
                headers=request_headers,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                raise Exception(f"MCP tools/list error: {result['error']}")

            return result.get("result", {}).get("tools", [])

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            headers: Optional headers including X-User-Scopes for authorization

        Returns:
            Tool execution result

        Raises:
            Exception: If tool call fails or scope is insufficient
        """
        logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")

        # Ensure Accept header is set for Kong AI MCP Proxy compatibility
        request_headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                json={
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
                headers=request_headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Capture MCP token from response header
            mcp_token_header = response.headers.get("X-MCP-Token")
            if mcp_token_header:
                self.last_mcp_token = mcp_token_header
                logger.info(f"Captured MCP token from response header")

            if "error" in result:
                error = result["error"]
                error_msg = error.get("message", "Unknown error")
                error_data = error.get("data", {})

                logger.error(f"MCP tool call error: {error_msg}, data: {error_data}")
                raise Exception(f"Tool '{tool_name}' failed: {error_msg}")

            # Extract text content from MCP response
            content = result.get("result", {}).get("content", [])
            if content and len(content) > 0:
                return content[0].get("text", "")

            return result.get("result", {})
