"""Database models for Research OS."""
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class ResearchPhase(str, Enum):
    """Phases of the research process."""
    PLANNING = "planning"
    SEARCHING = "searching"
    CRAWLING = "crawling"
    CURATING = "curating"
    EXTRACTING = "extracting"
    BUILDING_GRAPH = "building_graph"
    VERIFYING = "verifying"
    DEBATING = "debating"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    ERROR = "error"


class SourceType(str, Enum):
    """Types of sources."""
    WEBPAGE = "webpage"
    PDF = "pdf"
    ACADEMIC = "academic"
    NEWS = "news"
    BLOG = "blog"
    UNKNOWN = "unknown"


class VerificationMethod(str, Enum):
    """Methods used to verify claims."""
    EXACT = "exact"
    SEMANTIC = "semantic"
    NLI = "nli"
    NONE = "none"


class EvidenceLevel(str, Enum):
    """Evidence hierarchy for medical mode."""
    SYSTEMATIC_REVIEW = "systematic_review"
    RCT = "rct"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    EXPERT_OPINION = "expert_opinion"
    UNKNOWN = "unknown"


# ============== Database Models ==============

class Source(BaseModel):
    """A research source (webpage, PDF, etc.)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    title: Optional[str] = None
    text: Optional[str] = None  # Extracted text content
    html: Optional[str] = None  # Raw HTML
    content_hash: str  # SHA-256 hash for deduplication
    
    # Metadata
    source_type: SourceType = SourceType.UNKNOWN
    domain: Optional[str] = None
    credibility_score: float = 0.5  # 0-1
    credibility_factors: Dict[str, float] = Field(default_factory=dict)
    
    # Content analysis
    word_count: int = 0
    has_citations: bool = False
    has_methodology: bool = False
    publish_date: Optional[datetime] = None
    
    # Medical mode
    evidence_level: Optional[EvidenceLevel] = None
    pico: Optional[Dict[str, str]] = None  # Population, Intervention, Comparison, Outcome
    
    # Timestamps
    fetched_at: datetime = Field(default_factory=_utc_now)
    created_at: datetime = Field(default_factory=_utc_now)
    
    class Config:
        from_attributes = True


class Claim(BaseModel):
    """An extracted factual claim."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    text: str
    
    # Analysis
    confidence: float = 0.5  # Agent's confidence in extraction
    entities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    
    # Verification
    verified: bool = False
    verification_method: VerificationMethod = VerificationMethod.NONE
    verification_confidence: float = 0.0
    source_excerpt: Optional[str] = None  # The text that verifies this claim
    
    # Medical
    evidence_level: Optional[EvidenceLevel] = None
    
    # Graph
    embedding: Optional[List[float]] = None  # Vector embedding
    
    created_at: datetime = Field(default_factory=_utc_now)
    
    class Config:
        from_attributes = True


class ClaimRelation(BaseModel):
    """Relationship between two claims."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_claim_id: str
    target_claim_id: str
    relation_type: str  # "SUPPORTS", "CONTRADICTS", "RELATED_TO"
    confidence: float = 0.5
    explanation: Optional[str] = None
    created_at: datetime = Field(default_factory=_utc_now)
    
    class Config:
        from_attributes = True


class AgentActivity(BaseModel):
    """Record of an agent's activity."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    agent_name: str  # "scout", "skeptic", "analyst", "synthesizer"
    activity_type: str  # "search", "analyze", "extract", "debate", "synthesize"
    status: str  # "started", "in_progress", "completed", "error"
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    
    class Config:
        from_attributes = True


class DebateRound(BaseModel):
    """A round of agent debate."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    round_number: int
    agent_name: str
    position: str
    argument: str
    evidence_claim_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    created_at: datetime = Field(default_factory=_utc_now)
    
    class Config:
        from_attributes = True


class ResearchSession(BaseModel):
    """A complete research session."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    mode: str = "standard"  # "quick", "standard", "deep", "medical"
    
    # Status
    phase: ResearchPhase = ResearchPhase.PLANNING
    status: str = "active"  # "active", "paused", "completed", "error"
    progress_percent: int = 0
    
    # Configuration
    target_sources: int = 50
    max_sources: int = 100
    enable_debate: bool = True
    
    # Results
    subqueries: List[str] = Field(default_factory=list)
    source_count: int = 0
    claim_count: int = 0
    debate_rounds: int = 0
    final_report: Optional[str] = None
    
    # Graph data (serialized)
    graph_data: Optional[Dict[str, Any]] = None
    
    # Timing
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============== WebSocket Events ==============

class ResearchEvent(BaseModel):
    """Base class for research events sent via WebSocket."""
    type: str
    session_id: str
    timestamp: datetime = Field(default_factory=_utc_now)


class StatusEvent(ResearchEvent):
    """Status update event."""
    type: str = "status"
    phase: ResearchPhase
    message: str
    progress_percent: int


class SourceEvent(ResearchEvent):
    """New source discovered."""
    type: str = "source"
    source: Source


class ClaimEvent(ResearchEvent):
    """New claim extracted."""
    type: str = "claim"
    claim: Claim
    agent_name: str


class GraphUpdateEvent(ResearchEvent):
    """Knowledge graph updated."""
    type: str = "graph"
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class DebateEvent(ResearchEvent):
    """Debate round update."""
    type: str = "debate"
    round_number: int
    agent_name: str
    argument: str
    confidence: float


class ReportEvent(ResearchEvent):
    """Final report ready."""
    type: str = "report"
    markdown: str
    complete: bool = True


class ErrorEvent(ResearchEvent):
    """Error occurred."""
    type: str = "error"
    message: str
    details: Optional[str] = None
