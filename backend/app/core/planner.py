"""
Research Planning Module
Uses LLM to understand user intent, suggest angles, and decompose queries
"""
import httpx
import json
import structlog
from typing import List, Dict, Any

from app.core.config import settings

logger = structlog.get_logger()


async def _llm_generate(prompt: str, format_json: bool = True) -> str:
    """
    Generate text using the configured LLM provider.

    Args:
        prompt: The prompt to send
        format_json: Whether to request JSON output

    Returns:
        Generated text response
    """
    async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
        if settings.llm_provider == "openrouter":
            return await _generate_openrouter(client, prompt, format_json)
        else:
            return await _generate_ollama(client, prompt, format_json)


async def _generate_openrouter(client: httpx.AsyncClient, prompt: str, format_json: bool) -> str:
    """Generate using OpenRouter API."""
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://research-os.local",
        "X-Title": "Research OS"
    }

    payload = {
        "model": settings.model_default,  # Use default model for planning
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": settings.max_tokens,
    }

    if format_json:
        payload["response_format"] = {"type": "json_object"}

    response = await client.post(
        f"{settings.openrouter_base_url}/chat/completions",
        headers=headers,
        json=payload
    )
    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"]


async def _generate_ollama(client: httpx.AsyncClient, prompt: str, format_json: bool) -> str:
    """Generate using Ollama API."""
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }

    if format_json:
        payload["format"] = "json"

    response = await client.post(
        f"{settings.ollama_url}/api/generate",
        json=payload
    )
    response.raise_for_status()

    result = response.json()
    return result["response"]


async def understand_query(original_query: str) -> Dict[str, Any]:
    """
    Use LLM to understand and rewrite the user's query
    """
    prompt = f"""You are a research assistant helping to understand a user's research query.

Original query: "{original_query}"

Your task:
1. Analyze what the user is really asking for
2. Rewrite the query to be more specific and researchable
3. Identify the key concepts and entities

Respond in JSON format:
{{
  "understood_query": "A clearer, more specific version of the query",
  "key_concepts": ["concept1", "concept2", ...],
  "research_domain": "e.g., medicine, technology, finance, etc.",
  "clarification_needed": false,
  "suggested_clarification": "If clarification is needed, what to ask"
}}

Make the understood_query comprehensive but focused. It should capture the full intent."""

    try:
        response_text = await _llm_generate(prompt, format_json=True)
        data = json.loads(response_text)
        return {
            "understood_query": data.get("understood_query", original_query),
            "key_concepts": data.get("key_concepts", []),
            "research_domain": data.get("research_domain", "general"),
            "clarification_needed": data.get("clarification_needed", False),
            "suggested_clarification": data.get("suggested_clarification", "")
        }
    except Exception as e:
        logger.error(f"Error understanding query: {e}")
        return {
            "understood_query": original_query,
            "key_concepts": [],
            "research_domain": "general",
            "clarification_needed": False,
            "suggested_clarification": ""
        }


async def suggest_research_angles(understood_query: str, domain: str = "general") -> List[str]:
    """
    Suggest different angles/perspectives for researching the topic
    """
    prompt = f"""You are a research strategist. Given a research topic, suggest different angles or perspectives to explore.

Research topic: "{understood_query}"
Domain: {domain}

Suggest 6-8 different research angles that would provide comprehensive coverage. Each angle should be a specific perspective or aspect to investigate.

Respond in JSON format:
{{
  "angles": [
    "Angle 1: specific perspective",
    "Angle 2: specific perspective",
    ...
  ]
}}

Make angles concrete and actionable for web research."""

    try:
        response_text = await _llm_generate(prompt, format_json=True)
        data = json.loads(response_text)
        return data.get("angles", get_default_angles(domain))
    except Exception as e:
        logger.error(f"Error suggesting angles: {e}")
        return get_default_angles(domain)


def get_default_angles(domain: str) -> List[str]:
    """Default research angles by domain"""
    angles_by_domain = {
        "medicine": [
            "Clinical trials and efficacy data",
            "Safety profile and side effects",
            "Mechanism of action",
            "Comparative effectiveness",
            "Patient outcomes and real-world evidence",
            "Regulatory status and guidelines"
        ],
        "technology": [
            "Technical architecture and implementation",
            "Performance benchmarks and comparisons",
            "Adoption and use cases",
            "Security and privacy considerations",
            "Future roadmap and development",
            "Competitive landscape"
        ],
        "finance": [
            "Market performance and trends",
            "Risk analysis and mitigation",
            "Regulatory environment",
            "Comparative analysis with alternatives",
            "Economic impact assessment",
            "Future projections"
        ],
        "general": [
            "Current state and key findings",
            "Historical context and evolution",
            "Different perspectives and viewpoints",
            "Recent developments and trends",
            "Key stakeholders and their positions",
            "Future implications and directions"
        ]
    }
    return angles_by_domain.get(domain, angles_by_domain["general"])


async def decompose_into_subquestions(
    understood_query: str, 
    selected_angles: List[str]
) -> List[str]:
    """
    Break down the research into specific sub-questions
    """
    angles_text = "\n".join([f"- {angle}" for angle in selected_angles])
    
    prompt = f"""You are a research planner. Given a research topic and selected angles, break this down into specific sub-questions that can be researched independently.

Research topic: "{understood_query}"

Selected angles:
{angles_text}

Create 4-6 specific sub-questions. Each should be:
- Clear and specific
- Researchable via web search
- Cover a distinct aspect
- Together provide comprehensive coverage

Respond in JSON format:
{{
  "sub_questions": [
    "Specific sub-question 1?",
    "Specific sub-question 2?",
    ...
  ]
}}

Make sub-questions concrete enough that someone could search for each one independently."""

    try:
        response_text = await _llm_generate(prompt, format_json=True)
        data = json.loads(response_text)
        return data.get("sub_questions", [understood_query])
    except Exception as e:
        logger.error(f"Error decomposing query: {e}")
        return [understood_query]


async def generate_search_queries(sub_questions: List[str]) -> List[str]:
    """
    Convert sub-questions into actual search queries
    """
    all_queries = []
    
    for sq in sub_questions:
        # Add the sub-question as a query
        all_queries.append(sq)
        # Add variations
        all_queries.append(f"{sq} 2024")
        all_queries.append(f"{sq} recent research")
    
    return all_queries[:15]  # Limit to 15 queries
