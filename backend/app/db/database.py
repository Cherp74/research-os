"""Database operations for Research OS."""
import sqlite3
import json
import numpy as np
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Generator
import structlog

from app.db.models import (
    Source, Claim, ClaimRelation, ResearchSession,
    AgentActivity, DebateRound
)

logger = structlog.get_logger()


class ResearchDatabase:
    """SQLite database with vector support for Research OS."""
    
    def __init__(self, db_path: str = "data/research.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection with proper settings and automatic cleanup.

        This context manager ensures connections are properly closed after use,
        preventing resource leaks. It also handles transaction commit/rollback.

        Yields:
            sqlite3.Connection: A configured database connection.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Try to load sqlite-vec extension
        try:
            conn.enable_load_extension(True)
            conn.load_extension("vec0")
        except sqlite3.OperationalError:
            logger.warning("sqlite-vec extension not available, using fallback")

        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            # Sources table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    text TEXT,
                    html TEXT,
                    content_hash TEXT UNIQUE NOT NULL,
                    source_type TEXT DEFAULT 'unknown',
                    domain TEXT,
                    credibility_score REAL DEFAULT 0.5,
                    credibility_factors TEXT,
                    word_count INTEGER DEFAULT 0,
                    has_citations INTEGER DEFAULT 0,
                    has_methodology INTEGER DEFAULT 0,
                    publish_date TEXT,
                    evidence_level TEXT,
                    pico TEXT,
                    fetched_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Claims table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    entities TEXT,
                    keywords TEXT,
                    verified INTEGER DEFAULT 0,
                    verification_method TEXT DEFAULT 'none',
                    verification_confidence REAL DEFAULT 0.0,
                    source_excerpt TEXT,
                    evidence_level TEXT,
                    embedding BLOB,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_id) REFERENCES sources(id)
                )
            """)
            
            # Claim relations table (for knowledge graph)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claim_relations (
                    id TEXT PRIMARY KEY,
                    source_claim_id TEXT NOT NULL,
                    target_claim_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    explanation TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_claim_id) REFERENCES claims(id),
                    FOREIGN KEY (target_claim_id) REFERENCES claims(id),
                    UNIQUE(source_claim_id, target_claim_id, relation_type)
                )
            """)
            
            # Research sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    mode TEXT DEFAULT 'standard',
                    phase TEXT DEFAULT 'planning',
                    status TEXT DEFAULT 'active',
                    progress_percent INTEGER DEFAULT 0,
                    target_sources INTEGER DEFAULT 50,
                    max_sources INTEGER DEFAULT 100,
                    enable_debate INTEGER DEFAULT 1,
                    subqueries TEXT,
                    source_count INTEGER DEFAULT 0,
                    claim_count INTEGER DEFAULT 0,
                    debate_rounds INTEGER DEFAULT 0,
                    final_report TEXT,
                    graph_data TEXT,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)
            
            # Agent activities table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_activities (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES research_sessions(id)
                )
            """)
            
            # Debate rounds table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debate_rounds (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    agent_name TEXT NOT NULL,
                    position TEXT,
                    argument TEXT NOT NULL,
                    evidence_claim_ids TEXT,
                    confidence REAL DEFAULT 0.5,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES research_sessions(id)
                )
            """)
            
            conn.commit()
            logger.info("Database initialized", path=str(self.db_path))
    
    # ============== Source Operations ==============
    
    def save_source(self, source: Source) -> str:
        """Save or update a source."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sources 
                (id, url, title, text, html, content_hash, source_type, domain,
                 credibility_score, credibility_factors, word_count, has_citations,
                 has_methodology, publish_date, evidence_level, pico, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source.id, source.url, source.title, source.text, source.html,
                source.content_hash, source.source_type, source.domain,
                source.credibility_score, json.dumps(source.credibility_factors),
                source.word_count, int(source.has_citations), int(source.has_methodology),
                source.publish_date.isoformat() if source.publish_date else None,
                source.evidence_level, json.dumps(source.pico) if source.pico else None,
                source.fetched_at.isoformat()
            ))
            conn.commit()
            return source.id
    
    def get_source(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
            
            if row:
                return self._row_to_source(row)
            return None
    
    def get_source_by_hash(self, content_hash: str) -> Optional[Source]:
        """Get a source by content hash (for deduplication)."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            
            if row:
                return self._row_to_source(row)
            return None
    
    def get_sources_by_session(self, session_id: str) -> List[Source]:
        """Get all sources for a session."""
        # For now, we'll query all sources (session association can be added later)
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sources ORDER BY credibility_score DESC"
            ).fetchall()
            return [self._row_to_source(row) for row in rows]
    
    def source_exists(self, content_hash: str) -> bool:
        """Check if a source with this hash already exists."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM sources WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            return row is not None
    
    # ============== Claim Operations ==============
    
    def save_claim(self, claim: Claim) -> str:
        """Save a claim."""
        with self._get_connection() as conn:
            # Serialize embedding if present
            embedding_blob = None
            if claim.embedding:
                embedding_blob = np.array(claim.embedding, dtype=np.float32).tobytes()
            
            conn.execute("""
                INSERT OR REPLACE INTO claims
                (id, source_id, text, confidence, entities, keywords, verified,
                 verification_method, verification_confidence, source_excerpt,
                 evidence_level, embedding, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim.id, claim.source_id, claim.text, claim.confidence,
                json.dumps(claim.entities), json.dumps(claim.keywords),
                int(claim.verified), claim.verification_method,
                claim.verification_confidence, claim.source_excerpt,
                claim.evidence_level, embedding_blob,
                claim.created_at.isoformat()
            ))
            conn.commit()
            return claim.id
    
    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Get a claim by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM claims WHERE id = ?", (claim_id,)
            ).fetchone()
            
            if row:
                return self._row_to_claim(row)
            return None
    
    def get_claims_by_source(self, source_id: str) -> List[Claim]:
        """Get all claims from a source."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE source_id = ?", (source_id,)
            ).fetchall()
            return [self._row_to_claim(row) for row in rows]
    
    def get_all_claims(self) -> List[Claim]:
        """Get all claims."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM claims").fetchall()
            return [self._row_to_claim(row) for row in rows]
    
    # ============== Claim Relation Operations ==============
    
    def save_claim_relation(self, relation: ClaimRelation) -> str:
        """Save a claim relation."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO claim_relations
                (id, source_claim_id, target_claim_id, relation_type, confidence, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                relation.id, relation.source_claim_id, relation.target_claim_id,
                relation.relation_type, relation.confidence, relation.explanation
            ))
            conn.commit()
            return relation.id
    
    def get_claim_relations(self, claim_id: str) -> List[ClaimRelation]:
        """Get all relations for a claim."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM claim_relations 
                WHERE source_claim_id = ? OR target_claim_id = ?
            """, (claim_id, claim_id)).fetchall()
            return [self._row_to_claim_relation(row) for row in rows]
    
    def get_all_claim_relations(self) -> List[ClaimRelation]:
        """Get all claim relations."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM claim_relations").fetchall()
            return [self._row_to_claim_relation(row) for row in rows]
    
    # ============== Research Session Operations ==============
    
    def create_session(self, query: str, mode: str = "standard", 
                       target_sources: int = 50) -> ResearchSession:
        """Create a new research session."""
        session = ResearchSession(
            query=query,
            mode=mode,
            target_sources=target_sources
        )
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO research_sessions
                (id, query, mode, phase, status, progress_percent,
                 target_sources, max_sources, enable_debate, subqueries,
                 started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.id, session.query, session.mode, session.phase,
                session.status, session.progress_percent,
                session.target_sources, session.max_sources,
                int(session.enable_debate), json.dumps(session.subqueries),
                session.started_at.isoformat()
            ))
            conn.commit()
        
        return session
    
    def get_session(self, session_id: str) -> Optional[ResearchSession]:
        """Get a research session by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM research_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            
            if row:
                return self._row_to_research_session(row)
            return None
    
    def update_session(self, session: ResearchSession):
        """Update a research session."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE research_sessions SET
                    phase = ?, status = ?, progress_percent = ?,
                    subqueries = ?, source_count = ?, claim_count = ?,
                    debate_rounds = ?, final_report = ?, graph_data = ?,
                    completed_at = ?
                WHERE id = ?
            """, (
                session.phase, session.status, session.progress_percent,
                json.dumps(session.subqueries), session.source_count,
                session.claim_count, session.debate_rounds,
                session.final_report, json.dumps(session.graph_data) if session.graph_data else None,
                session.completed_at.isoformat() if session.completed_at else None,
                session.id
            ))
            conn.commit()
    
    def list_sessions(self, limit: int = 50) -> List[ResearchSession]:
        """List recent research sessions."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM research_sessions ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [self._row_to_research_session(row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        """Delete a research session and its associated data."""
        with self._get_connection() as conn:
            # Delete associated debate rounds
            conn.execute(
                "DELETE FROM debate_rounds WHERE session_id = ?", (session_id,)
            )
            # Delete associated agent activities
            conn.execute(
                "DELETE FROM agent_activities WHERE session_id = ?", (session_id,)
            )
            # Delete the session itself
            cursor = conn.execute(
                "DELETE FROM research_sessions WHERE id = ?", (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # ============== Agent Activity Operations ==============
    
    def log_agent_activity(self, activity: AgentActivity) -> str:
        """Log an agent activity."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO agent_activities
                (id, session_id, agent_name, activity_type, status, message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                activity.id, activity.session_id, activity.agent_name,
                activity.activity_type, activity.status, activity.message,
                json.dumps(activity.metadata) if activity.metadata else None
            ))
            conn.commit()
            return activity.id
    
    def get_session_activities(self, session_id: str) -> List[AgentActivity]:
        """Get all activities for a session."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_activities WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            ).fetchall()
            return [self._row_to_agent_activity(row) for row in rows]
    
    # ============== Debate Operations ==============
    
    def save_debate_round(self, debate: DebateRound) -> str:
        """Save a debate round."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO debate_rounds
                (id, session_id, round_number, agent_name, position, argument,
                 evidence_claim_ids, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                debate.id, debate.session_id, debate.round_number,
                debate.agent_name, debate.position, debate.argument,
                json.dumps(debate.evidence_claim_ids), debate.confidence
            ))
            conn.commit()
            return debate.id
    
    def get_session_debates(self, session_id: str) -> List[DebateRound]:
        """Get all debate rounds for a session."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM debate_rounds WHERE session_id = ? ORDER BY round_number",
                (session_id,)
            ).fetchall()
            return [self._row_to_debate_round(row) for row in rows]
    
    # ============== Helper Methods ==============
    
    def _row_to_source(self, row: sqlite3.Row) -> Source:
        """Convert database row to Source model."""
        return Source(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            text=row["text"],
            html=row["html"],
            content_hash=row["content_hash"],
            source_type=row["source_type"],
            domain=row["domain"],
            credibility_score=row["credibility_score"],
            credibility_factors=json.loads(row["credibility_factors"]) if row["credibility_factors"] else {},
            word_count=row["word_count"],
            has_citations=bool(row["has_citations"]),
            has_methodology=bool(row["has_methodology"]),
            publish_date=datetime.fromisoformat(row["publish_date"]) if row["publish_date"] else None,
            evidence_level=row["evidence_level"],
            pico=json.loads(row["pico"]) if row["pico"] else None,
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            created_at=datetime.fromisoformat(row["created_at"])
        )
    
    def _row_to_claim(self, row: sqlite3.Row) -> Claim:
        """Convert database row to Claim model."""
        embedding = None
        if row["embedding"]:
            embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()
        
        return Claim(
            id=row["id"],
            source_id=row["source_id"],
            text=row["text"],
            confidence=row["confidence"],
            entities=json.loads(row["entities"]) if row["entities"] else [],
            keywords=json.loads(row["keywords"]) if row["keywords"] else [],
            verified=bool(row["verified"]),
            verification_method=row["verification_method"],
            verification_confidence=row["verification_confidence"],
            source_excerpt=row["source_excerpt"],
            evidence_level=row["evidence_level"],
            embedding=embedding,
            created_at=datetime.fromisoformat(row["created_at"])
        )
    
    def _row_to_claim_relation(self, row: sqlite3.Row) -> ClaimRelation:
        """Convert database row to ClaimRelation model."""
        return ClaimRelation(
            id=row["id"],
            source_claim_id=row["source_claim_id"],
            target_claim_id=row["target_claim_id"],
            relation_type=row["relation_type"],
            confidence=row["confidence"],
            explanation=row["explanation"],
            created_at=datetime.fromisoformat(row["created_at"])
        )
    
    def _row_to_research_session(self, row: sqlite3.Row) -> ResearchSession:
        """Convert database row to ResearchSession model."""
        return ResearchSession(
            id=row["id"],
            query=row["query"],
            mode=row["mode"],
            phase=row["phase"],
            status=row["status"],
            progress_percent=row["progress_percent"],
            target_sources=row["target_sources"],
            max_sources=row["max_sources"],
            enable_debate=bool(row["enable_debate"]),
            subqueries=json.loads(row["subqueries"]) if row["subqueries"] else [],
            source_count=row["source_count"],
            claim_count=row["claim_count"],
            debate_rounds=row["debate_rounds"],
            final_report=row["final_report"],
            graph_data=json.loads(row["graph_data"]) if row["graph_data"] else None,
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        )
    
    def _row_to_agent_activity(self, row: sqlite3.Row) -> AgentActivity:
        """Convert database row to AgentActivity model."""
        return AgentActivity(
            id=row["id"],
            session_id=row["session_id"],
            agent_name=row["agent_name"],
            activity_type=row["activity_type"],
            status=row["status"],
            message=row["message"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"])
        )
    
    def _row_to_debate_round(self, row: sqlite3.Row) -> DebateRound:
        """Convert database row to DebateRound model."""
        return DebateRound(
            id=row["id"],
            session_id=row["session_id"],
            round_number=row["round_number"],
            agent_name=row["agent_name"],
            position=row["position"],
            argument=row["argument"],
            evidence_claim_ids=json.loads(row["evidence_claim_ids"]) if row["evidence_claim_ids"] else [],
            confidence=row["confidence"],
            created_at=datetime.fromisoformat(row["created_at"])
        )


# Singleton instance
db = ResearchDatabase()
