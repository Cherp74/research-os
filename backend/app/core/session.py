"""Research session state machine."""
from typing import Optional, List, Dict, Any, AsyncGenerator
from enum import Enum, auto
import asyncio
import structlog
from datetime import datetime, UTC

from app.db.models import (
    ResearchSession, ResearchPhase, Source, Claim, 
    StatusEvent, SourceEvent, ClaimEvent, GraphUpdateEvent,
    DebateEvent, ReportEvent, ErrorEvent
)
from app.db.database import db
from app.core.search import search_engine
from app.core.crawler import crawler
from app.core.curator import curator, CurationResult
from app.core.knowledge_graph import KnowledgeGraph
from app.core.verifier import verifier
from app.core.debate import DebateOrchestrator, DebateResult
from app.agents.specialized import (
    ScoutAgent, SkepticAgent, AnalystAgent, SynthesizerAgent,
    create_agent_swarm
)
from app.agents.base import AgentResult

logger = structlog.get_logger()


class ResearchSessionManager:
    """
    Manages a complete research session from query to report.
    
    This is the main orchestrator that coordinates all components.
    """
    
    def __init__(self, session: ResearchSession, websocket=None):
        self.session = session
        self.websocket = websocket
        self.knowledge_graph = KnowledgeGraph()
        self.debate_orchestrator = DebateOrchestrator()
        
        # Agents
        self.scout = ScoutAgent()
        self.skeptic = SkepticAgent()
        self.analyst = AnalystAgent()
        self.synthesizer = SynthesizerAgent()
        
        # State
        self.sources: List[Source] = []
        self.claims: List[Claim] = []
        self.crawled_content = []
        
        # HTTP client for agents
        self.http_client = None  # Will be created in run()
    
    async def emit(self, event: Any):
        """Emit event to WebSocket if connected."""
        if self.websocket:
            try:
                # Use model_dump with mode='json' for proper serialization
                data = event.model_dump(mode='json')
                await self.websocket.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")
    
    async def update_phase(self, phase: ResearchPhase, message: str, progress: int):
        """Update session phase and emit status."""
        self.session.phase = phase
        self.session.progress_percent = progress
        db.update_session(self.session)
        
        await self.emit(StatusEvent(
            type="status",
            session_id=self.session.id,
            phase=phase,
            message=message,
            progress_percent=progress
        ))
        
        logger.info(f"Phase: {phase} - {message}", progress=progress)
    
    async def run(self) -> ResearchSession:
        """
        Run the complete research pipeline.
        
        Returns:
            Completed ResearchSession
        """
        import httpx
        self.http_client = httpx.AsyncClient(timeout=120.0)
        
        try:
            # Phase 1: Planning
            await self.update_phase(
                ResearchPhase.PLANNING,
                "Decomposing query into sub-queries...",
                5
            )
            await self._planning()
            
            # Phase 2: Searching
            await self.update_phase(
                ResearchPhase.SEARCHING,
                f"Searching for sources (target: {self.session.target_sources})...",
                10
            )
            search_results = await self._search()
            
            # Phase 3: Crawling
            await self.update_phase(
                ResearchPhase.CRAWLING,
                f"Crawling {len(search_results)} URLs...",
                20
            )
            await self._crawl(search_results)
            
            # Phase 4: Curation
            await self.update_phase(
                ResearchPhase.CURATING,
                "Filtering and ranking sources...",
                30
            )
            await self._curate()
            
            # Phase 5: Claim Extraction
            await self.update_phase(
                ResearchPhase.EXTRACTING,
                "Extracting claims with multiple agents...",
                45
            )
            await self._extract_claims()
            
            # Phase 6: Build Knowledge Graph
            await self.update_phase(
                ResearchPhase.BUILDING_GRAPH,
                "Building knowledge graph...",
                60
            )
            await self._build_graph()
            
            # Phase 7: Verification
            await self.update_phase(
                ResearchPhase.VERIFYING,
                "Verifying claims against sources...",
                70
            )
            await self._verify_claims()
            
            # Phase 8: Debate (conditional)
            contradictions = self.knowledge_graph.find_contradictions()
            debate_result = None
            
            if self.session.enable_debate and len(contradictions) >= 1:
                await self.update_phase(
                    ResearchPhase.DEBATING,
                    f"Debating {len(contradictions)} contradictions...",
                    80
                )
                debate_result = await self._debate(contradictions)
            
            # Phase 9: Synthesis
            await self.update_phase(
                ResearchPhase.SYNTHESIZING,
                "Generating final report...",
                90
            )
            await self._synthesize(debate_result)
            
            # Complete
            await self.update_phase(
                ResearchPhase.COMPLETE,
                "Research complete!",
                100
            )
            
            self.session.status = "completed"
            self.session.completed_at = datetime.now(UTC)
            db.update_session(self.session)
            
        except Exception as e:
            logger.error(f"Research session error: {e}", exc_info=True)
            self.session.status = "error"
            self.session.phase = ResearchPhase.ERROR
            db.update_session(self.session)
            
            await self.emit(ErrorEvent(
                type="error",
                session_id=self.session.id,
                message="Research failed",
                details=str(e)
            ))
        
        finally:
            await self.http_client.aclose()
            await self._close_agents()
        
        return self.session
    
    async def _planning(self):
        """Plan the research: decompose query."""
        # Simple query expansion for now
        # Could use LLM for more sophisticated planning
        subqueries = [
            self.session.query,
            f"{self.session.query} recent research",
            f"{self.session.query} evidence",
        ]
        
        self.session.subqueries = subqueries
        logger.info(f"Planned subqueries: {subqueries}")
    
    async def _search(self) -> List[Dict]:
        """Search for sources."""
        all_results = []
        
        for query in self.session.subqueries:
            results = await search_engine.search(query, max_results=15)
            all_results.extend(results)
            
            logger.info(f"Search '{query[:30]}...' found {len(results)} results")
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        return unique_results[:self.session.max_sources * 2]  # Get extra for curation
    
    async def _crawl(self, search_results: List[Dict]):
        """Crawl discovered URLs."""
        urls = [r.url for r in search_results]
        
        crawled = await crawler.crawl_multiple(urls)
        self.crawled_content = [c for c in crawled if c.success]
        
        # Emit sources as they're crawled
        for i, content in enumerate(self.crawled_content):
            await self.emit(SourceEvent(
                type="source",
                session_id=self.session.id,
                source=Source(
                    url=content.url,
                    title=content.title,
                    content_hash=content.content_hash,
                    word_count=content.word_count
                )
            ))
        
        logger.info(f"Crawled {len(self.crawled_content)} sources successfully")
    
    async def _curate(self):
        """Curate sources: deduplicate, rank, filter."""
        result: CurationResult = curator.curate(
            self.crawled_content,
            self.session.query,
            max_sources=self.session.target_sources
        )
        
        self.sources = result.sources
        
        # Save sources to DB
        for source in self.sources:
            db.save_source(source)
        
        self.session.source_count = len(self.sources)
        
        logger.info(
            f"Curation complete: {len(self.sources)} sources "
            f"(removed {result.duplicates_removed} duplicates, "
            f"{result.low_quality_removed} low quality)"
        )
    
    async def _extract_claims(self):
        """Extract claims using multiple agents."""
        # Run agents in parallel
        agents = [self.scout, self.skeptic, self.analyst]
        
        tasks = [
            agent.analyze(self.session.query, self.sources)
            for agent in agents
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        all_claims = []
        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent.name} failed: {result}")
                continue
            
            # Convert agent claims to Claim models
            for claim_data in result.claims:
                # Find source_id from source_index or use first source
                source_id = self.sources[0].id if self.sources else "unknown"
                if "source_id" in claim_data:
                    source_id = claim_data["source_id"]
                elif "source_index" in claim_data:
                    idx = claim_data["source_index"]
                    if 0 <= idx < len(self.sources):
                        source_id = self.sources[idx].id
                
                claim = Claim(
                    source_id=source_id,
                    text=claim_data["text"],
                    confidence=claim_data.get("confidence", 0.5),
                    entities=claim_data.get("entities", []),
                    keywords=claim_data.get("keywords", [])
                )
                
                all_claims.append(claim)
                
                # Emit claim event
                await self.emit(ClaimEvent(
                    type="claim",
                    session_id=self.session.id,
                    claim=claim,
                    agent_name=agent.name
                ))
        
        self.claims = all_claims
        self.session.claim_count = len(all_claims)
        
        logger.info(f"Extracted {len(all_claims)} claims from {len(agents)} agents")
    
    async def _build_graph(self):
        """Build knowledge graph from claims."""
        # Create source lookup
        source_lookup = {s.id: s for s in self.sources}
        
        for claim in self.claims:
            source = source_lookup.get(claim.source_id)
            self.knowledge_graph.add_claim(claim, source)
        
        # Emit graph update
        graph_data = self.knowledge_graph.to_vis_data()
        await self.emit(GraphUpdateEvent(
            type="graph",
            session_id=self.session.id,
            nodes=graph_data["nodes"],
            edges=graph_data["edges"]
        ))
        
        stats = self.knowledge_graph.get_statistics()
        logger.info(f"Knowledge graph: {stats}")
    
    async def _verify_claims(self):
        """Verify all claims against their sources."""
        source_lookup = {s.id: s for s in self.sources}
        
        verified_claims = []
        for claim in self.claims:
            source = source_lookup.get(claim.source_id)
            if source:
                verified, method, confidence, excerpt = verifier.verify_claim(
                    claim, source, use_nli=False  # Skip NLI for speed
                )
                claim.verified = verified
                claim.verification_method = method
                claim.verification_confidence = confidence
                claim.source_excerpt = excerpt
            
            verified_claims.append(claim)
            db.save_claim(claim)
        
        self.claims = verified_claims
        
        verified_count = sum(1 for c in self.claims if c.verified)
        logger.info(f"Verification: {verified_count}/{len(self.claims)} claims verified")
    
    async def _debate(self, contradictions: List) -> DebateResult:
        """Conduct debate on contradictory evidence."""
        # Get agent results for context
        agent_results = {
            "scout": AgentResult(agent_name="scout", claims=[], summary=""),
            "skeptic": AgentResult(agent_name="skeptic", claims=[], summary=""),
            "analyst": AgentResult(agent_name="analyst", claims=[], summary=""),
        }
        
        # Get actual claims for contradictions
        claim_lookup = {c.id: c for c in self.claims}
        contradiction_claims = []
        
        for c1_id, c2_id, conf in contradictions[:3]:  # Top 3
            c1 = claim_lookup.get(c1_id)
            c2 = claim_lookup.get(c2_id)
            if c1 and c2:
                contradiction_claims.append((c1, c2, conf))
        
        debate_result = await self.debate_orchestrator.conduct_debate(
            self.session.query,
            contradiction_claims,
            agent_results,
            self.http_client
        )
        
        # Save debate rounds
        debate_rounds = self.debate_orchestrator.to_debate_rounds(
            debate_result, self.session.id
        )
        for dr in debate_rounds:
            db.save_debate_round(dr)
        
        self.session.debate_rounds = len(debate_result.rounds)
        
        # Emit debate events
        for round_positions in debate_result.rounds:
            for pos in round_positions:
                await self.emit(DebateEvent(
                    type="debate",
                    session_id=self.session.id,
                    round_number=debate_result.rounds.index(round_positions) + 1,
                    agent_name=pos.agent_name,
                    argument=pos.argument,
                    confidence=pos.confidence
                ))
        
        logger.info(f"Debate complete: consensus={debate_result.consensus_reached}")
        return debate_result
    
    async def _synthesize(self, debate_result: Optional[DebateResult]):
        """Generate final report."""
        # Build agent results from claims
        agent_results = {
            "scout": AgentResult(
                agent_name="scout",
                claims=[{"text": c.text, "confidence": c.confidence} for c in self.claims],
                summary=f"Found {len(self.claims)} claims from {len(self.sources)} sources"
            ),
            "skeptic": AgentResult(agent_name="skeptic", claims=[], summary=""),
            "analyst": AgentResult(agent_name="analyst", claims=[], summary=""),
        }
        
        graph_data = {
            "statistics": self.knowledge_graph.get_statistics(),
            "visualization": self.knowledge_graph.to_vis_data()
        }
        
        report = await self.synthesizer.synthesize(
            self.session.query,
            agent_results,
            graph_data,
            self.knowledge_graph.find_contradictions(),
            debate_result=debate_result
        )
        
        self.session.final_report = report
        
        # Save graph data
        self.session.graph_data = graph_data["visualization"]
        
        # Emit report
        await self.emit(ReportEvent(
            type="report",
            session_id=self.session.id,
            markdown=report,
            complete=True
        ))
        
        logger.info("Synthesis complete")
    
    async def _close_agents(self):
        """Close all agent connections."""
        await self.scout.close()
        await self.skeptic.close()
        await self.analyst.close()
        await self.synthesizer.close()


async def create_research_session(
    query: str,
    mode: str = "standard",
    target_sources: int = 30,
    websocket=None
) -> ResearchSessionManager:
    """
    Create and return a new research session manager.
    
    Args:
        query: Research query
        mode: "quick", "standard", "deep", "medical"
        target_sources: Target number of sources
        websocket: Optional WebSocket for streaming
        
    Returns:
        ResearchSessionManager ready to run
    """
    # Create session in DB
    session = db.create_session(query, mode, target_sources)
    
    # Configure based on mode
    if mode == "quick":
        session.target_sources = 15
        session.max_sources = 30
        session.enable_debate = False
    elif mode == "deep":
        session.target_sources = 50
        session.max_sources = 100
        session.enable_debate = True
    elif mode == "medical":
        session.target_sources = 40
        session.max_sources = 80
        session.enable_debate = True
    
    db.update_session(session)
    
    return ResearchSessionManager(session, websocket)
