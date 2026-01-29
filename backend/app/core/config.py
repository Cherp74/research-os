"""Configuration for Research OS."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Provider
    llm_provider: str = "ollama"  # "openrouter" or "ollama"

    # OpenRouter settings
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Model configuration for different agents
    model_scout: str = "google/gemini-flash-1.5"
    model_skeptic: str = "deepseek/deepseek-chat"
    model_analyst: str = "qwen/qwen-2.5-72b-instruct"
    model_synthesizer: str = "anthropic/claude-opus-4-20250514"
    model_default: str = "google/gemini-flash-1.5"

    # Ollama settings (fallback)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # Search settings
    search_provider: str = "openrouter"  # "openrouter", "tavily", or "duckduckgo"
    tavily_api_key: Optional[str] = None

    # Request settings
    llm_timeout: int = 300  # seconds
    max_tokens: int = 4000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_model_for_agent(agent_name: str) -> str:
    """Get the configured model for a specific agent."""
    model_map = {
        "scout": settings.model_scout,
        "skeptic": settings.model_skeptic,
        "analyst": settings.model_analyst,
        "synthesizer": settings.model_synthesizer,
    }
    return model_map.get(agent_name, settings.model_default)
