"""Specialized research agents."""
from typing import List, Dict, Any, Optional
import json
import structlog

from app.agents.base import BaseAgent, AgentResult
from app.db.models import Source, Claim

logger = structlog.get_logger()


class ScoutAgent(BaseAgent):
    """
    Scout agent: Finds diverse, recent, and broad coverage.
    Looks for emerging trends, breaking news, and diverse perspectives.
    """
    
    def __init__(self, model: str = "qwen2.5:7b"):
        super().__init__("scout", model)
        self.system_prompt = """You are a research scout. Your job is to find diverse, recent, 
and broad coverage of topics. Look for emerging trends, breaking news, and diverse perspectives.

When analyzing sources:
1. Identify the main claims and findings
2. Look for recent developments and trends
3. Note diverse viewpoints and perspectives
4. Flag emerging or controversial topics
5. Identify key entities (people, organizations, concepts)

Output your findings as structured JSON with claims, entities, and a brief summary."""
    
    async def analyze(
        self, 
        query: str, 
        sources: List[Source],
        **kwargs
    ) -> AgentResult:
        """Scout analysis: broad coverage and trends."""
        
        # Prepare source summaries for the agent
        source_texts = []
        for i, source in enumerate(sources[:15]):  # Limit to top 15 for context
            source_texts.append(f"""
Source {i+1}: {source.title or 'Untitled'}
URL: {source.url}
Credibility: {source.credibility_score:.2f}
Content: {source.text[:1500] if source.text else 'No content'}
""")
        
        prompt = f"""{self.system_prompt}

Research Query: {query}

Sources to analyze:
{chr(10).join(source_texts)}

Analyze these sources and extract:
1. Key factual claims (with confidence scores 0-1)
2. Important entities mentioned
3. Emerging trends or recent developments
4. Diverse perspectives on the topic

Respond in this JSON format:
{{
  "claims": [
    {{"text": "specific claim", "confidence": 0.8, "source_indices": [1, 3]}},
    ...
  ],
  "entities": ["entity1", "entity2", ...],
  "trends": ["trend1", "trend2", ...],
  "summary": "brief summary of findings"
}}"""
        
        try:
            response = await self.generate(prompt, temperature=0.4, format_json=True)
            data = json.loads(response)
            
            # Convert to AgentResult
            claims = []
            for claim_data in data.get("claims", []):
                claims.append({
                    "text": claim_data.get("text", ""),
                    "confidence": claim_data.get("confidence", 0.5),
                    "source_indices": claim_data.get("source_indices", []),
                    "agent": self.name
                })
            
            return AgentResult(
                agent_name=self.name,
                claims=claims,
                entities=data.get("entities", []),
                summary=data.get("summary", ""),
                confidence=0.7,
                metadata={"trends": data.get("trends", [])}
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Scout JSON parse error: {e}", response=response[:500])
            # Fallback: return empty result
            return AgentResult(
                agent_name=self.name,
                summary="Error parsing scout analysis",
                confidence=0.0
            )
        except Exception as e:
            logger.error(f"Scout analysis error: {e}")
            return AgentResult(
                agent_name=self.name,
                summary=f"Error: {str(e)}",
                confidence=0.0
            )


class SkepticAgent(BaseAgent):
    """
    Skeptic agent: Finds gaps, biases, and contradictions.
    Questions methodology, funding sources, and sample sizes.
    """
    
    def __init__(self, model: str = "qwen2.5:7b"):
        super().__init__("skeptic", model)
        self.system_prompt = """You are a research skeptic. Your job is to find gaps, biases, 
and contradictions in the evidence. Question methodology, funding sources, and sample sizes.

When analyzing sources:
1. Identify methodological flaws or limitations
2. Look for potential biases (funding, selection, confirmation)
3. Find contradictory evidence or alternative explanations
4. Question sample sizes and statistical significance
5. Check for missing context or cherry-picked data
6. Identify claims that are overstated or premature

Output your critical analysis as structured JSON."""
    
    async def analyze(
        self, 
        query: str, 
        sources: List[Source],
        **kwargs
    ) -> AgentResult:
        """Skeptic analysis: critical evaluation."""
        
        source_texts = []
        for i, source in enumerate(sources[:15]):
            # Add credibility context for skeptic
            credibility_flags = []
            if source.credibility_score < 0.4:
                credibility_flags.append("LOW_CREDIBILITY")
            if not source.has_methodology:
                credibility_flags.append("NO_METHODOLOGY")
            if not source.has_citations:
                credibility_flags.append("NO_CITATIONS")
            
            source_texts.append(f"""
Source {i+1}: {source.title or 'Untitled'}
URL: {source.url}
Domain: {source.domain}
Credibility: {source.credibility_score:.2f}
Flags: {', '.join(credibility_flags) if credibility_flags else 'None'}
Content: {source.text[:1500] if source.text else 'No content'}
""")
        
        prompt = f"""{self.system_prompt}

Research Query: {query}

Sources to critically analyze:
{chr(10).join(source_texts)}

Provide a critical analysis:
1. Identify potential biases in the sources
2. Find methodological limitations
3. Look for contradictory claims or evidence
4. Flag overstated or unsupported claims
5. Identify gaps in the evidence

Respond in this JSON format:
{{
  "biases": ["bias1", "bias2", ...],
  "limitations": ["limitation1", ...],
  "contradictions": [
    {{"claim_a": "...", "claim_b": "...", "explanation": "..."}},
    ...
  ],
  "unsupported_claims": ["claim1", ...],
  "evidence_gaps": ["gap1", ...],
  "claims": [
    {{"text": "critical observation", "confidence": 0.7, "type": "critique"}}
  ],
  "summary": "critical summary"
}}"""
        
        try:
            response = await self.generate(prompt, temperature=0.3, format_json=True)
            data = json.loads(response)
            
            claims = []
            for claim_data in data.get("claims", []):
                claims.append({
                    "text": claim_data.get("text", ""),
                    "confidence": claim_data.get("confidence", 0.5),
                    "type": claim_data.get("type", "critique"),
                    "agent": self.name
                })
            
            return AgentResult(
                agent_name=self.name,
                claims=claims,
                summary=data.get("summary", ""),
                confidence=0.6,  # Skeptic is naturally less confident
                metadata={
                    "biases": data.get("biases", []),
                    "limitations": data.get("limitations", []),
                    "contradictions": data.get("contradictions", []),
                    "evidence_gaps": data.get("evidence_gaps", [])
                }
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Skeptic JSON parse error: {e}")
            return AgentResult(
                agent_name=self.name,
                summary="Error parsing skeptic analysis",
                confidence=0.0
            )
        except Exception as e:
            logger.error(f"Skeptic analysis error: {e}")
            return AgentResult(
                agent_name=self.name,
                summary=f"Error: {str(e)}",
                confidence=0.0
            )


class AnalystAgent(BaseAgent):
    """
    Analyst agent: Extracts structured claims, entities, and relationships.
    Focuses on factual precision and evidence quality.
    """
    
    def __init__(self, model: str = "qwen2.5:7b"):
        super().__init__("analyst", model)
        self.system_prompt = """You are a research analyst. Extract structured claims, 
entities, and relationships with high precision. Focus on: who said what, based on what evidence.

When analyzing sources:
1. Extract specific, verifiable factual claims
2. Identify key entities (people, organizations, concepts, metrics)
3. Note evidence quality and methodology
4. Extract numerical data with units
5. Identify cause-effect relationships
6. Flag uncertainty and confidence levels

Be precise and factual. Avoid speculation."""
    
    async def analyze(
        self, 
        query: str, 
        sources: List[Source],
        **kwargs
    ) -> AgentResult:
        """Analyst analysis: structured extraction."""
        
        # Process each source individually for detailed extraction
        all_claims = []
        all_entities = set()
        
        for i, source in enumerate(sources[:10]):  # Process top 10 in detail
            if not source.text:
                continue
            
            prompt = f"""{self.system_prompt}

Research Query: {query}

Source: {source.title or 'Untitled'}
URL: {source.url}
Credibility: {source.credibility_score:.2f}
Has Citations: {source.has_citations}
Has Methodology: {source.has_methodology}

Content:
{source.text[:2000]}

Extract structured information:
1. Factual claims with confidence (0-1)
2. Key entities mentioned
3. Numerical data points
4. Methodology notes

Respond in JSON:
{{
  "claims": [
    {{
      "text": "specific factual claim",
      "confidence": 0.85,
      "has_numbers": true,
      "methodology": "brief method note or null"
    }}
  ],
  "entities": ["entity1", "entity2"],
  "numbers": ["value with unit"],
  "source_quality": "high/medium/low"
}}"""
            
            try:
                response = await self.generate(prompt, temperature=0.2, format_json=True)
                data = json.loads(response)
                
                for claim_data in data.get("claims", []):
                    all_claims.append({
                        "text": claim_data.get("text", ""),
                        "confidence": claim_data.get("confidence", 0.5) * source.credibility_score,
                        "source_index": i,
                        "source_id": source.id,
                        "has_numbers": claim_data.get("has_numbers", False),
                        "methodology": claim_data.get("methodology"),
                        "agent": self.name
                    })
                
                all_entities.update(data.get("entities", []))
                
            except Exception as e:
                logger.warning(f"Error analyzing source {source.url}: {e}")
                continue
        
        # Generate overall summary
        summary_prompt = f"""Based on the following extracted claims about "{query}", 
provide a brief analytical summary (2-3 sentences):

Claims:
{chr(10).join([c['text'] for c in all_claims[:10]])}

Summary:"""
        
        try:
            summary = await self.generate(summary_prompt, temperature=0.3)
        except:
            summary = f"Extracted {len(all_claims)} claims from {len(sources)} sources."
        
        return AgentResult(
            agent_name=self.name,
            claims=all_claims,
            entities=list(all_entities),
            summary=summary.strip(),
            confidence=0.75,
            metadata={"total_claims": len(all_claims)}
        )


class SynthesizerAgent(BaseAgent):
    """
    Synthesizer agent: Creates final report from all agent outputs and knowledge graph.
    This is the "Chairman" agent that produces the final output.
    """

    def __init__(self, model: str = "qwen2.5:7b"):
        super().__init__("synthesizer", model)
        self.system_prompt = """You are a research synthesizer. Your job is to create
a comprehensive, well-cited research report from multiple agent analyses and a knowledge graph.

Your report should:
1. Present key findings with confidence levels
2. Acknowledge contradictions and uncertainties
3. Cite sources for every major claim
4. Note evidence quality and limitations
5. Organize by themes or topics
6. Include an executive summary

Be balanced, objective, and intellectually honest about uncertainty."""

    async def analyze(
        self,
        query: str,
        sources: List[Source],
        **kwargs
    ) -> AgentResult:
        """
        Synthesizer doesn't analyze sources directly - it synthesizes other agent outputs.
        This method exists to satisfy the abstract base class requirement.
        """
        return AgentResult(
            agent_name=self.name,
            summary="Synthesizer does not analyze sources directly. Use synthesize() method.",
            confidence=0.0
        )

    async def synthesize(
        self,
        query: str,
        agent_results: Dict[str, AgentResult],
        knowledge_graph_data: Dict[str, Any],
        contradictions: List[tuple],
        **kwargs
    ) -> str:
        """Synthesize final report from all inputs."""
        
        # Build context from agent results
        agent_contexts = []
        for name, result in agent_results.items():
            agent_contexts.append(f"""
=== {name.upper()} ANALYSIS ===
Summary: {result.summary}
Claims found: {len(result.claims)}
Entities: {', '.join(result.entities[:10])}
Key claims:
{chr(10).join([f"- {c['text'][:200]} (confidence: {c.get('confidence', 0.5):.2f})" for c in result.claims[:5]])}
""")
        
        # Add contradiction context
        contradiction_context = ""
        if contradictions:
            contradiction_context = f"""
=== CONTRADICTORY EVIDENCE ===
{len(contradictions)} contradictions were identified in the knowledge graph.
These represent genuine disagreements in the sources that should be acknowledged.
"""
        
        # Add graph statistics
        graph_stats = knowledge_graph_data.get("statistics", {})
        graph_context = f"""
=== KNOWLEDGE GRAPH ===
Total nodes: {graph_stats.get('total_nodes', 0)}
Claims: {graph_stats.get('claim_nodes', 0)}
Entities: {graph_stats.get('entity_nodes', 0)}
Sources: {graph_stats.get('source_nodes', 0)}
Supporting relationships: {graph_stats.get('supports_edges', 0)}
Contradictory relationships: {graph_stats.get('contradicts_edges', 0)}
"""
        
        prompt = f"""{self.system_prompt}

Research Query: {query}

{graph_context}

{contradiction_context}

{chr(10).join(agent_contexts)}

Create a comprehensive research report in Markdown format with the following sections:

# Executive Summary
3-5 bullet points of key findings with confidence levels

# Key Findings
Organized by theme/topic, with inline citations [Source: URL]

# Areas of Agreement
What do most sources agree on?

# Areas of Disagreement  
What are the genuine controversies or uncertainties?

# Evidence Quality
Assessment of source quality and limitations

# Conclusion
Synthesized conclusion with confidence level

Format all citations as [Source: URL] for verification."""
        
        try:
            report = await self.generate(prompt, temperature=0.3)
            return report
        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            return f"# Error\nFailed to synthesize report: {str(e)}"


# Factory function for creating the agent swarm
def create_agent_swarm(model: str = "qwen2.5:7b") -> List[BaseAgent]:
    """Create the full agent swarm."""
    return [
        ScoutAgent(model),
        SkepticAgent(model),
        AnalystAgent(model)
    ]
