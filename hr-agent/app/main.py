"""FastAPI application for HR Agent."""
import logging
import base64
import json
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.auth import TokenContext, get_token_context
from app.agent import HRAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT payload without verification (for display purposes)."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Add padding if needed
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding

        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        return json.loads(payload_json)
    except Exception as e:
        logger.error(f"Error decoding JWT: {e}")
        return None


# Request/Response models
class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    chat_history: Optional[List[ChatMessage]] = None


class TokenInfo(BaseModel):
    """Token information model."""
    token: str
    claims: Optional[Dict[str, Any]] = None
    hop: int  # Which hop in the exchange chain (1 = first exchange to HR Agent)
    description: str


class ExchangedTokensInfo(BaseModel):
    """Container for multiple exchanged tokens."""
    tokens: List[TokenInfo]


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    user_scopes: List[str]
    user_sub: str
    exchanged_token: Optional[ExchangedTokensInfo] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting HR Agent service...")
    logger.info(f"LLM API URL: {settings.llm_api_url} (Kong AI Proxy)")
    logger.info(f"MCP Server URL: {settings.mcp_server_url}")
    yield
    logger.info("Shutting down HR Agent service...")


# Create FastAPI app
app = FastAPI(
    title="HR Agent",
    description="AI Agent for HR operations using Claude and MCP",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="hr-agent",
        version="1.0.0",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    token_context: TokenContext = Depends(get_token_context),
    raw_request: Request = None,
):
    """
    Chat endpoint for interacting with the HR Agent.

    The agent will:
    1. Receive user scopes from Kong Gateway via headers
    2. Create LangChain agent with only authorized tools
    3. Process user query using Claude
    4. Call MCP tools as needed (with scope enforcement)
    5. Return response to user

    Args:
        request: Chat request with message and optional history
        token_context: Token context injected by FastAPI dependency
        raw_request: Raw FastAPI request to inspect headers

    Returns:
        Chat response with agent's reply
    """
    try:
        # Log ALL headers to see where Kong might be sending the exchanged token
        logger.info("\n" + "="*80)
        logger.info("[TOKEN_DEBUG] ALL HEADERS received by HR Agent from Kong:")
        logger.info("="*80)
        for header_name, header_value in raw_request.headers.items():
            # Truncate long values for readability
            display_value = header_value[:100] + "..." if len(header_value) > 100 else header_value
            logger.info(f"  {header_name}: {display_value}")
        logger.info("="*80 + "\n")
        logger.info(
            f"Chat request from user {token_context.user_sub} "
            f"with scopes: {token_context.scopes_list}"
        )

        # Create agent instance
        agent = HRAgent(token_context)

        # Convert chat history to dict format
        chat_history = []
        if request.chat_history:
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.chat_history
            ]

        # Process message
        response = await agent.chat(request.message, chat_history)

        # Extract token from x-introspection-token header (Hop 1: HR Agent token)
        # Kong sends the exchanged token in x-introspection-token header (base64-encoded RFC 8693 response)
        exchanged_tokens = []

        # Use the exchanged token from token_context (already extracted from x-introspection-token)
        token = token_context.exchanged_token

        # Fallback to Authorization header if no exchanged token found
        if not token and token_context.authorization:
            logger.warning("[TOKEN] No exchanged token found, falling back to Authorization header")
            token = token_context.authorization
            if token.startswith('Bearer '):
                token = token[7:]
            elif token.startswith('bearer '):
                token = token[7:]

        if token:
            # Decode the token
            token_claims = decode_jwt_payload(token)

            # Log token details for debugging
            logger.info(f"\n[TOKEN_DEBUG] Hop 1 - HR Agent received token from Kong:")
            logger.info(f"  Token preview: {token[:20]}...{token[-20:]}")
            logger.info(f"  Audience (aud): {token_claims.get('aud') if token_claims else 'Failed to decode'}")
            logger.info(f"  Subject (sub): {token_claims.get('sub') if token_claims else 'Failed to decode'}")
            logger.info(f"  Scopes: {token_claims.get('scope') if token_claims else 'Failed to decode'}")

            exchanged_tokens.append(TokenInfo(
                token=token,
                claims=token_claims,
                hop=1,
                description='Token exchanged by Kong OIDC for HR Agent (Hop 1: Flask UI → HR Agent)'
            ))

        # Extract MCP token if available (Hop 2: MCP Server token)
        if agent.mcp_client.last_mcp_token:
            mcp_token = agent.mcp_client.last_mcp_token

            # Remove 'Bearer ' prefix if present
            if mcp_token.startswith('Bearer '):
                mcp_token = mcp_token[7:]
            elif mcp_token.startswith('bearer '):
                mcp_token = mcp_token[7:]

            # Decode the token
            mcp_token_claims = decode_jwt_payload(mcp_token)

            # Log token details for debugging
            logger.info(f"\n[TOKEN_DEBUG] Hop 2 - MCP Server token captured:")
            logger.info(f"  Audience (aud): {mcp_token_claims.get('aud') if mcp_token_claims else 'Failed to decode'}")
            logger.info(f"  Subject (sub): {mcp_token_claims.get('sub') if mcp_token_claims else 'Failed to decode'}")
            logger.info(f"  Scopes: {mcp_token_claims.get('scope') if mcp_token_claims else 'Failed to decode'}")

            exchanged_tokens.append(TokenInfo(
                token=mcp_token,
                claims=mcp_token_claims,
                hop=2,
                description='Token exchanged by Kong OIDC for MCP Server (Hop 2: HR Agent → MCP Server)'
            ))

        return ChatResponse(
            response=response,
            user_scopes=token_context.scopes_list,
            user_sub=token_context.user_sub,
            exchanged_token=ExchangedTokensInfo(tokens=exchanged_tokens) if exchanged_tokens else None,
        )

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}",
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "HR Agent",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
