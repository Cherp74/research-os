"""Debate orchestration for handling contradictory evidence."""
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import json
import structlog

from app.agents.base import BaseAgent, AgentResult
from app.db.models import Claim, DebateRound

logger = structlog.get_logger()


@dataclass
class DebatePosition:
    """A position in a debate."""
    agent_name: str
    position: str  # "for", "against", "neutral"
    argument: str
    evidence_claim_ids: List[str]
    confidence: float


@dataclass
class DebateResult:
    """Result of a debate."""
    rounds: List[List[DebatePosition]]
    consensus_reached: bool
    winning_position: Optional[str]
    confidence: float
    summary: str


class DebateOrchestrator:
    """
    Orchestrate agent debates when contradictory evidence is found.
    
    Protocol:
    1. Round 1: Each agent presents position
    2. Round 2: Agents rebut each other's positions (if needed)
    3. Resolution: Determine if consensus or genuine disagreement
    """
    
    def __init__(self, model: str = "qwen2.5:7b", ollama_url: str = "http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url
        self.min_confidence_gap = 0.3  # Threshold for triggering debate
        self.consensus_threshold = 0.7  # Confidence for consensus
    
    async def should_debate(
        self, 
        contradictions: List[Tuple[str, str, float]],
        agent_results: Dict[str, AgentResult]
    ) -> bool:
        """
        Determine if debate is needed.
        
        Args:
            contradictions: List of contradictory claim pairs
            agent_results: Results from all agents
            
        Returns:
            True if debate should be triggered
        """
        # Debate if there are contradictions
        if len(contradictions) >= 2:
            logger.info(f"Triggering debate: {len(contradictions)} contradictions found")
            return True
        
        # Debate if agents have significantly different confidence
        confidences = [r.confidence for r in agent_results.values()]
        if len(confidences) >= 2:
            gap = max(confidences) - min(confidences)
            if gap > self.min_confidence_gap:
                logger.info(f"Triggering debate: confidence gap {gap:.2f}")
                return True
        
        return False
    
    async def conduct_debate(
        self,
        query: str,
        contradictory_claims: List[Tuple[Claim, Claim, float]],
        agent_results: Dict[str, AgentResult],
        http_client  # Pass HTTP client for Ollama
    ) -> DebateResult:
        """
        Conduct a multi-round debate.
        
        Args:
            query: Research query
            contradictory_claims: List of (claim1, claim2, confidence) tuples
            agent_results: Agent analysis results
            http_client: HTTP client for API calls
            
        Returns:
            DebateResult with positions and resolution
        """
        logger.info(f"Starting debate on: {query[:50]}")
        
        rounds = []
        
        # Round 1: Position statements
        round1 = await self._round1_positions(
            query, contradictory_claims, agent_results, http_client
        )
        rounds.append(round1)
        
        # Check for early consensus
        consensus_check = self._check_consensus(round1)
        if consensus_check[0]:
            return DebateResult(
                rounds=rounds,
                consensus_reached=True,
                winning_position=consensus_check[1],
                confidence=consensus_check[2],
                summary="Early consensus reached after initial positions."
            )
        
        # Round 2: Rebuttals
        round2 = await self._round2_rebuttals(
            query, round1, http_client
        )
        rounds.append(round2)
        
        # Final resolution
        resolution = self._resolve_debate(rounds)
        
        return DebateResult(
            rounds=rounds,
            consensus_reached=resolution["consensus"],
            winning_position=resolution.get("position"),
            confidence=resolution["confidence"],
            summary=resolution["summary"]
        )
    
    async def _round1_positions(
        self,
        query: str,
        contradictions: List[Tuple[Claim, Claim, float]],
        agent_results: Dict[str, AgentResult],
        http_client
    ) -> List[DebatePosition]:
        """Round 1: Agents present their positions."""
        
        # Format contradiction context
        contradiction_text = ""
        for i, (c1, c2, conf) in enumerate(contradictions[:3]):  # Top 3
            contradiction_text += f"""
Contradiction {i+1} (confidence: {conf:.2f}):
- Claim A: {c1.text}
- Claim B: {c2.text}
"""
        
        # Get positions from each agent's perspective
        positions = []
        
        for agent_name, result in agent_results.items():
            prompt = f"""You are the {agent_name} agent in a research debate.

Research Query: {query}

Key Contradictions in Evidence:
{contradiction_text}

Your previous analysis: {result.summary}

Your task: Present your position on these contradictions.
- What is your assessment of the conflicting evidence?
- Which side do you lean toward and why?
- What is your confidence level (0-1)?

Respond in JSON:
{{
  "position": "brief position statement (1-2 sentences)",
  "stance": "for_claim_a/for_claim_b/uncertain",
  "confidence": 0.75,
  "reasoning": "brief reasoning"
}}"""
            
            try:
                response = await http_client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.3}
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                result_json = json.loads(data["response"])
                
                positions.append(DebatePosition(
                    agent_name=agent_name,
                    position=result_json.get("position", ""),
                    argument=result_json.get("reasoning", ""),
                    evidence_claim_ids=[],  # Would populate from actual claims
                    confidence=result_json.get("confidence", 0.5)
                ))
                
            except Exception as e:
                logger.error(f"Debate round 1 error for {agent_name}: {e}")
                positions.append(DebatePosition(
                    agent_name=agent_name,
                    position="Error generating position",
                    argument=str(e),
                    evidence_claim_ids=[],
                    confidence=0.0
                ))
        
        return positions
    
    async def _round2_rebuttals(
        self,
        query: str,
        round1_positions: List[DebatePosition],
        http_client
    ) -> List[DebatePosition]:
        """Round 2: Agents rebut each other's positions."""
        
        # Format other agents' positions
        others_positions = ""
        for pos in round1_positions:
            others_positions += f"""
{pos.agent_name}: {pos.position} (confidence: {pos.confidence:.2f})
"""
        
        rebuttals = []
        
        for pos in round1_positions:
            prompt = f"""You are the {pos.agent_name} agent responding to other agents' positions.

Research Query: {query}
Your position: {pos.position}

Other agents' positions:
{others_positions}

Your task: Provide a brief rebuttal or acknowledgment.
- Do you agree with any other positions?
- Do you disagree? Why?
- Has your confidence changed?

Respond in JSON:
{{
  "rebuttal": "your response",
  "confidence_change": "increased/decreased/unchanged",
  "new_confidence": 0.7
}}"""
            
            try:
                response = await http_client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.3}
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                result = json.loads(data["response"])
                
                rebuttals.append(DebatePosition(
                    agent_name=pos.agent_name,
                    position=pos.position,
                    argument=result.get("rebuttal", ""),
                    evidence_claim_ids=pos.evidence_claim_ids,
                    confidence=result.get("new_confidence", pos.confidence)
                ))
                
            except Exception as e:
                logger.error(f"Debate round 2 error for {pos.agent_name}: {e}")
                rebuttals.append(pos)  # Use original position
        
        return rebuttals
    
    def _check_consensus(
        self, 
        positions: List[DebatePosition]
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if consensus has been reached.
        
        Returns: (consensus_reached, winning_position, confidence)
        """
        if len(positions) < 2:
            return True, positions[0].position if positions else None, 1.0
        
        confidences = [p.confidence for p in positions]
        avg_confidence = sum(confidences) / len(confidences)
        
        # High average confidence = consensus
        if avg_confidence > self.consensus_threshold:
            # Find most confident position
            best = max(positions, key=lambda p: p.confidence)
            return True, best.position, best.confidence
        
        # Check if all positions are similar (would need semantic comparison)
        return False, None, avg_confidence
    
    def _resolve_debate(
        self, 
        rounds: List[List[DebatePosition]]
    ) -> Dict[str, Any]:
        """
        Resolve the debate and determine final position.
        
        Returns resolution dict.
        """
        if not rounds:
            return {
                "consensus": False,
                "confidence": 0.0,
                "summary": "No debate rounds conducted."
            }
        
        final_round = rounds[-1]
        confidences = [p.confidence for p in final_round]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Determine if genuine disagreement or uncertainty
        confidence_variance = max(confidences) - min(confidences) if confidences else 0
        
        if confidence_variance < 0.2 and avg_confidence > 0.5:
            # Rough consensus
            best = max(final_round, key=lambda p: p.confidence)
            return {
                "consensus": True,
                "position": best.position,
                "confidence": avg_confidence,
                "summary": f"Consensus reached with average confidence {avg_confidence:.2f}."
            }
        else:
            # Genuine disagreement
            positions_summary = " | ".join([
                f"{p.agent_name}: {p.position[:50]}..." 
                for p in final_round
            ])
            return {
                "consensus": False,
                "position": None,
                "confidence": avg_confidence,
                "summary": f"Genuine disagreement among agents. Positions: {positions_summary}"
            }
    
    def to_debate_rounds(
        self, 
        debate_result: DebateResult, 
        session_id: str
    ) -> List[DebateRound]:
        """Convert DebateResult to database DebateRound models."""
        rounds = []
        
        for round_num, positions in enumerate(debate_result.rounds):
            for pos in positions:
                rounds.append(DebateRound(
                    session_id=session_id,
                    round_number=round_num + 1,
                    agent_name=pos.agent_name,
                    position=pos.position,
                    argument=pos.argument,
                    evidence_claim_ids=pos.evidence_claim_ids,
                    confidence=pos.confidence
                ))
        
        return rounds
