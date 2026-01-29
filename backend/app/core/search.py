"""Multi-engine search functionality with retry logic and timeout handling."""
import asyncio
import random
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog
import httpx

# Use the new ddgs package (renamed from duckduckgo_search)
from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class SearchResult:
    """A search result."""
    title: str
    url: str
    snippet: str
    source: str = "duckduckgo"
    rank: int = 0


@dataclass
class SearchConfig:
    """Configuration for search engine."""
    timeout: float = 30.0
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 10.0
    # Timeout for individual DDGS operations (shorter than overall timeout)
    ddgs_timeout: int = 15


class SearchEngine:
    """Multi-engine search with fallback and retry logic."""

    def __init__(self, config: Optional[SearchConfig] = None):
        self.config = config or SearchConfig()
        self._last_search_time = 0.0
        self._min_request_interval = 1.0  # Minimum seconds between requests
    
    async def search(
        self,
        query: str,
        max_results: int = 20,
        recency_days: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Search using multiple engines with fallback.

        Args:
            query: Search query
            max_results: Maximum results to return
            recency_days: Filter by recency (optional)

        Returns:
            List of search results
        """
        results = []

        # Try OpenRouter web search first if configured
        if settings.search_provider == "openrouter" and settings.openrouter_api_key:
            try:
                or_results = await self._search_openrouter(query, max_results)
                results.extend(or_results)
                logger.info(
                    "OpenRouter web search completed",
                    query=query,
                    result_count=len(or_results)
                )
                if len(results) >= max_results:
                    return results[:max_results]
            except Exception as e:
                logger.warning(
                    "OpenRouter search failed, falling back",
                    query=query,
                    error=str(e)
                )

        # Try Tavily if configured
        if settings.search_provider == "tavily" and settings.tavily_api_key:
            try:
                tavily_results = await self._search_tavily(query, max_results - len(results))
                results.extend(tavily_results)
                logger.info(
                    "Tavily search completed",
                    query=query,
                    result_count=len(tavily_results)
                )
                if len(results) >= max_results:
                    return results[:max_results]
            except Exception as e:
                logger.warning(
                    "Tavily search failed, falling back to DuckDuckGo",
                    query=query,
                    error=str(e)
                )

        # Fall back to DuckDuckGo
        try:
            ddgs_results = await self._search_duckduckgo_with_retry(
                query, max_results - len(results), recency_days
            )
            results.extend(ddgs_results)
            logger.info(
                "DuckDuckGo search completed",
                query=query,
                result_count=len(ddgs_results)
            )
        except asyncio.TimeoutError:
            logger.warning(
                "DuckDuckGo search timed out after retries",
                query=query,
                timeout=self.config.timeout
            )
        except DDGSException as e:
            logger.warning(
                "DuckDuckGo search failed",
                query=query,
                error=str(e),
                error_type=type(e).__name__
            )
        except Exception as e:
            logger.error(
                "Unexpected error during DuckDuckGo search",
                query=query,
                error=str(e),
                error_type=type(e).__name__
            )

        return results[:max_results]

    async def _search_openrouter(
        self,
        query: str,
        max_results: int
    ) -> List[SearchResult]:
        """Search using OpenRouter web search plugin (Exa-powered)."""
        import json
        import re

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Use a fast model with web search plugin
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://research-os.local",
                    "X-Title": "Research OS"
                },
                json={
                    "model": "google/gemini-2.5-flash",
                    "plugins": [
                        {
                            "id": "web",
                            "max_results": max_results
                        }
                    ],
                    "messages": [
                        {
                            "role": "user",
                            "content": f"""Search the web for: {query}

Return a JSON array of the most relevant results. Each result should have:
- title: page title
- url: full URL
- snippet: brief description

Format:
```json
[{{"title": "...", "url": "...", "snippet": "..."}}, ...]
```

Return ONLY the JSON array, no other text."""
                        }
                    ],
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                results_data = json.loads(json_match.group())
                return [
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("snippet", ""),
                        source="openrouter",
                        rank=i
                    )
                    for i, r in enumerate(results_data)
                    if r.get("url")
                ]

            return []

    async def _search_tavily(
        self,
        query: str,
        max_results: int
    ) -> List[SearchResult]:
        """Search using Tavily API (AI-optimized search)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "include_answer": False,
                    "include_raw_content": False,
                }
            )
            response.raise_for_status()
            data = response.json()

            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                    source="tavily",
                    rank=i
                )
                for i, r in enumerate(data.get("results", []))
                if r.get("url")
            ]
    
    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_search_time
        if elapsed < self._min_request_interval:
            delay = self._min_request_interval - elapsed
            # Add jitter to prevent thundering herd
            delay += random.uniform(0.1, 0.5)
            await asyncio.sleep(delay)
        self._last_search_time = time.time()

    async def _search_duckduckgo_with_retry(
        self,
        query: str,
        max_results: int,
        recency_days: Optional[int] = None
    ) -> List[SearchResult]:
        """Search DuckDuckGo with retry logic."""
        last_exception: Optional[Exception] = None

        for attempt in range(self.config.max_retries):
            try:
                await self._rate_limit()
                return await self._search_duckduckgo(query, max_results, recency_days)
            except asyncio.TimeoutError as e:
                last_exception = e
                wait_time = min(
                    self.config.retry_max_wait,
                    self.config.retry_min_wait * (2 ** attempt)
                )
                # Add jitter
                wait_time += random.uniform(0, 1)
                logger.warning(
                    "DuckDuckGo search timeout, retrying",
                    query=query,
                    attempt=attempt + 1,
                    max_attempts=self.config.max_retries,
                    wait_seconds=round(wait_time, 2)
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(wait_time)
            except RatelimitException as e:
                last_exception = e
                # Rate limit errors should wait longer
                wait_time = self.config.retry_max_wait * (attempt + 1)
                logger.warning(
                    "DuckDuckGo rate limit hit, backing off",
                    query=query,
                    attempt=attempt + 1,
                    wait_seconds=wait_time
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(wait_time)
            except DDGSException as e:
                # Other DDGS exceptions might not benefit from retry
                last_exception = e
                raise
            except Exception as e:
                # Unexpected errors - don't retry
                raise

        # All retries exhausted
        if last_exception:
            raise last_exception
        return []

    async def _search_duckduckgo(
        self,
        query: str,
        max_results: int,
        recency_days: Optional[int] = None
    ) -> List[SearchResult]:
        """Search using DuckDuckGo."""
        # Run in thread pool since DDGS is synchronous
        loop = asyncio.get_running_loop()

        def _ddgs_search() -> List[Dict[str, Any]]:
            # Create DDGS instance with timeout
            with DDGS(timeout=self.config.ddgs_timeout) as ddgs:
                # Use text search
                results = ddgs.text(
                    query,
                    max_results=max_results,
                    region="wt-wt",  # Worldwide
                    safesearch="off"
                )
                return list(results) if results else []

        raw_results = await asyncio.wait_for(
            loop.run_in_executor(None, _ddgs_search),
            timeout=self.config.timeout
        )

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
                source="duckduckgo",
                rank=i
            )
            for i, r in enumerate(raw_results)
            if r.get("href")  # Filter out results without URLs
        ]
    
    async def search_multiple(
        self,
        queries: List[str],
        max_results_per_query: int = 10
    ) -> Dict[str, List[SearchResult]]:
        """
        Search multiple queries in parallel.
        
        Args:
            queries: List of search queries
            max_results_per_query: Max results per query
            
        Returns:
            Dict mapping query to results
        """
        tasks = [
            self.search(q, max_results_per_query)
            for q in queries
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            query: result if not isinstance(result, Exception) else []
            for query, result in zip(queries, results)
        }
    
    async def get_related_queries(self, query: str) -> List[str]:
        """
        Get related search queries to expand research.

        Args:
            query: Original query

        Returns:
            List of related queries
        """
        await self._rate_limit()

        loop = asyncio.get_running_loop()

        def _get_suggestions() -> List[str]:
            with DDGS(timeout=self.config.ddgs_timeout) as ddgs:
                suggestions = ddgs.suggestions(query)
                if suggestions:
                    return [s["phrase"] for s in suggestions]
                return []

        try:
            suggestions = await asyncio.wait_for(
                loop.run_in_executor(None, _get_suggestions),
                timeout=15.0  # Suggestions are usually faster
            )
            return suggestions[:5]  # Top 5 suggestions
        except asyncio.TimeoutError:
            logger.warning(
                "DuckDuckGo suggestions timed out",
                query=query
            )
            return []
        except DDGSException as e:
            logger.warning(
                "DuckDuckGo suggestions failed",
                query=query,
                error=str(e)
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error getting suggestions",
                query=query,
                error=str(e),
                error_type=type(e).__name__
            )
            return []


# Singleton instance
search_engine = SearchEngine()
