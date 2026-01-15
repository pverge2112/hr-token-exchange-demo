"""Configuration management for HR Agent."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001

    # LLM API settings (via Kong Gateway AI Proxy)
    # Kong handles provider, model, and API key via AI Proxy plugin
    llm_api_url: str = "http://kong-gateway:8000/api/llm"

    # MCP Server settings (always via Kong Gateway for token exchange)
    mcp_server_url: str = "http://kong-gateway:8000/mcp"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
