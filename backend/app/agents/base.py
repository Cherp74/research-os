"""Base agent class for Research OS."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
import json
import structlog
import httpx

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
    
    def __init__(self, name: str, model: str = "qwen2.5:7b", ollama_url: str = "http://localhost:11434"):
        self.name = name
        self.model = model
        self.ollama_url = ollama_url
        # Longer timeout for LLM operations (can take several minutes for large context)
        self.http_client = httpx.AsyncClient(timeout=300.0)
    
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.3,
        format_json: bool = False
    ) -> str:
        """
        Send a chat request to Ollama.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            format_json: Whether to enforce JSON output
            
        Returns:
            Response text
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 2000,
                }
            }
            
            if format_json:
                payload["format"] = "json"
            
            response = await self.http_client.post(
                f"{self.ollama_url}/api/chat",
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
        Generate text using Ollama generate endpoint.
        
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


import asyncio
