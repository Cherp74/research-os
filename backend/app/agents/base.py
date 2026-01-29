"""Base agent class for Research OS."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
import json
import structlog
import httpx
import asyncio

from app.core.config import settings, get_model_for_agent

logger = structlog.get_logger()


@dataclass
class AgentResult:
    """Result from an agent's analysis."""
    agent_name: str
    claims: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for research agents."""

    def __init__(self, name: str, model: Optional[str] = None):
        self.name = name
        # Use configured model for this agent, or override
        self.model = model or get_model_for_agent(name)
        self.provider = settings.llm_provider
        self.http_client = httpx.AsyncClient(timeout=settings.llm_timeout)

        logger.info(
            f"Agent initialized",
            agent=name,
            model=self.model,
            provider=self.provider
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        format_json: bool = False
    ) -> str:
        """
        Send a chat request to the configured LLM provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            format_json: Whether to enforce JSON output

        Returns:
            Response text
        """
        if self.provider == "openrouter":
            return await self._chat_openrouter(messages, temperature, format_json)
        else:
            return await self._chat_ollama(messages, temperature, format_json)

    async def _chat_openrouter(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        format_json: bool
    ) -> str:
        """Send chat request to OpenRouter."""
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://research-os.local",
            "X-Title": "Research OS"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": settings.max_tokens,
        }

        if format_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self.http_client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Log usage for cost tracking
            usage = result.get("usage", {})
            logger.debug(
                "OpenRouter response",
                agent=self.name,
                model=self.model,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens")
            )

            return content

        except httpx.HTTPStatusError as e:
            logger.error(
                f"OpenRouter HTTP error: {e.response.status_code}",
                agent=self.name,
                response=e.response.text[:500]
            )
            raise
        except Exception as e:
            logger.error(f"OpenRouter error: {e}", agent=self.name)
            raise

    async def _chat_ollama(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        format_json: bool
    ) -> str:
        """Send chat request to Ollama."""
        # Use ollama model instead of openrouter model name
        model = settings.ollama_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": settings.max_tokens,
            }
        }

        if format_json:
            payload["format"] = "json"

        try:
            response = await self.http_client.post(
                f"{settings.ollama_url}/api/chat",
                json=payload
            )
            response.raise_for_status()

            result = response.json()
            return result["message"]["content"]

        except httpx.HTTPError as e:
            logger.error(f"Ollama HTTP error: {e}", agent=self.name)
            raise
        except Exception as e:
            logger.error(f"Ollama error: {e}", agent=self.name)
            raise

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        format_json: bool = False
    ) -> str:
        """
        Generate text from a prompt.

        Args:
            prompt: The prompt
            temperature: Sampling temperature
            format_json: Whether to enforce JSON output

        Returns:
            Generated text
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature, format_json)

    @abstractmethod
    async def analyze(
        self,
        query: str,
        sources: List[Any],
        **kwargs
    ) -> AgentResult:
        """
        Analyze sources and return results.

        Args:
            query: Research query
            sources: List of sources to analyze
            **kwargs: Additional arguments

        Returns:
            AgentResult with claims, entities, etc.
        """
        pass

    async def stream_analysis(
        self,
        query: str,
        sources: List[Any],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream analysis progress.

        Yields progress updates as dicts.
        """
        # Default implementation just yields final result
        result = await self.analyze(query, sources, **kwargs)
        yield {
            "type": "agent_complete",
            "agent": self.name,
            "result": result
        }

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


class AgentOrchestrator:
    """Orchestrate multiple agents working in parallel."""

    def __init__(self, agents: List[BaseAgent]):
        self.agents = agents

    async def run_parallel(
        self,
        query: str,
        sources: List[Any],
        **kwargs
    ) -> Dict[str, AgentResult]:
        """
        Run all agents in parallel on the same sources.

        Args:
            query: Research query
            sources: Sources to analyze
            **kwargs: Additional arguments for agents

        Returns:
            Dict mapping agent name to result
        """
        logger.info(f"Running {len(self.agents)} agents in parallel", query=query[:50])

        tasks = [
            agent.analyze(query, sources, **kwargs)
            for agent in self.agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent.name} failed: {result}")
                output[agent.name] = AgentResult(
                    agent_name=agent.name,
                    summary=f"Error: {str(result)}",
                    confidence=0.0
                )
            else:
                output[agent.name] = result

        return output

    async def close(self):
        """Close all agents."""
        for agent in self.agents:
            await agent.close()
