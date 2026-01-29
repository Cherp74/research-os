"""FastAPI application for Research OS."""
from typing import List, Optional
from contextlib import asynccontextmanager
import structlog

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db.models import ResearchSession, Source, Claim
from app.db.database import db
from app.core.session import create_research_session, ResearchSessionManager
from app.core.planner import understand_query, suggest_research_angles, decompose_into_subquestions

logger = structlog.get_logger()


# ============== Pydantic Models ==============

class ResearchRequest(BaseModel):
    query: str
    mode: str = "standard"  # quick, standard, deep, medical
    target_sources: int = 30


class ResearchResponse(BaseModel):
    session_id: str
    query: str
    status: str
    phase: str
    progress_percent: int


class SessionListResponse(BaseModel):
    sessions: List[ResearchSession]


# Planning API Models
class PlanningUnderstandRequest(BaseModel):
    query: str


class PlanningUnderstandResponse(BaseModel):
    understood_query: str
    key_concepts: List[str]
    research_domain: str
    clarification_needed: bool
    suggested_clarification: str


class PlanningAnglesRequest(BaseModel):
    understood_query: str
    domain: str = "general"


class PlanningAnglesResponse(BaseModel):
    angles: List[str]


class PlanningDecomposeRequest(BaseModel):
    understood_query: str
    selected_angles: List[str]


class PlanningDecomposeResponse(BaseModel):
    sub_questions: List[str]


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Research OS starting up")
    yield
    logger.info("Research OS shutting down")


app = FastAPI(
    title="Research OS",
    description="Multi-agent research system with knowledge graph",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== REST Endpoints ==============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Research OS",
        "version": "1.0.0"
    }


@app.post("/api/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest):
    """
    Start a new research session (non-streaming).
    
    For real-time updates, use the WebSocket endpoint.
    """
    manager = await create_research_session(
        query=request.query,
        mode=request.mode,
        target_sources=request.target_sources
    )
    
    # Run research (this will block until complete)
    await manager.run()
    
    return ResearchResponse(
        session_id=manager.session.id,
        query=manager.session.query,
        status=manager.session.status,
        phase=manager.session.phase,
        progress_percent=manager.session.progress_percent
    )


@app.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = 50):
    """List recent research sessions."""
    sessions = db.list_sessions(limit)
    return SessionListResponse(sessions=sessions)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific research session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/api/sessions/{session_id}/report")
async def get_report(session_id: str):
    """Get the final report for a session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.final_report:
        raise HTTPException(status_code=404, detail="Report not yet available")
    
    return {"report": session.final_report}


@app.get("/api/sessions/{session_id}/graph")
async def get_graph(session_id: str):
    """Get knowledge graph data for a session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.graph_data:
        raise HTTPException(status_code=404, detail="Graph not yet available")
    
    return session.graph_data


@app.get("/api/sessions/{session_id}/sources")
async def get_sources(session_id: str):
    """Get sources for a session."""
    sources = db.get_sources_by_session(session_id)
    return {"sources": sources}


@app.get("/api/sessions/{session_id}/claims")
async def get_claims(session_id: str):
    """Get claims for a session."""
    # Get all claims (could filter by session in future)
    claims = db.get_all_claims()
    return {"claims": claims}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a research session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    deleted = db.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete session")

    return {"message": "Session deleted", "session_id": session_id}


# ============== Planning API Endpoints ==============

@app.post("/api/planning/understand", response_model=PlanningUnderstandResponse)
async def planning_understand(request: PlanningUnderstandRequest):
    """
    Step 1: AI understands and rewrites the user's query
    """
    logger.info(f"Planning - understanding query: {request.query[:50]}...")
    
    result = await understand_query(request.query)
    
    return PlanningUnderstandResponse(
        understood_query=result["understood_query"],
        key_concepts=result["key_concepts"],
        research_domain=result["research_domain"],
        clarification_needed=result["clarification_needed"],
        suggested_clarification=result["suggested_clarification"]
    )


@app.post("/api/planning/angles", response_model=PlanningAnglesResponse)
async def planning_angles(request: PlanningAnglesRequest):
    """
    Step 2: AI suggests research angles/perspectives
    """
    logger.info(f"Planning - suggesting angles for: {request.understood_query[:50]}...")
    
    angles = await suggest_research_angles(
        request.understood_query,
        request.domain
    )
    
    return PlanningAnglesResponse(angles=angles)


@app.post("/api/planning/decompose", response_model=PlanningDecomposeResponse)
async def planning_decompose(request: PlanningDecomposeRequest):
    """
    Step 3: AI decomposes into sub-questions
    """
    logger.info(f"Planning - decomposing query with {len(request.selected_angles)} angles")
    
    sub_questions = await decompose_into_subquestions(
        request.understood_query,
        request.selected_angles
    )
    
    return PlanningDecomposeResponse(sub_questions=sub_questions)


# ============== WebSocket Endpoint ==============

@app.websocket("/ws/research")
async def research_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time research streaming.
    
    Protocol:
    1. Client sends: {"query": "...", "mode": "standard", "target_sources": 30}
    2. Server streams events: status, source, claim, graph, debate, report
    3. Connection closes when complete or on error
    """
    await websocket.accept()
    manager: Optional[ResearchSessionManager] = None
    
    try:
        # Receive research request
        data = await websocket.receive_json()
        query = data.get("query", "")
        mode = data.get("mode", "standard")
        target_sources = data.get("target_sources", 30)
        
        if not query:
            await websocket.send_json({
                "type": "error",
                "message": "Query is required"
            })
            return
        
        logger.info(f"WebSocket research started: {query[:50]}...")
        
        # Create session manager with WebSocket
        manager = await create_research_session(
            query=query,
            mode=mode,
            target_sources=target_sources,
            websocket=websocket
        )
        
        # Send initial session info
        await websocket.send_json({
            "type": "session_created",
            "session_id": manager.session.id,
            "query": query,
            "mode": mode
        })
        
        # Run research (streams events via WebSocket)
        await manager.run()
        
        logger.info(f"WebSocket research complete: {manager.session.id}")
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


# ============== Additional Endpoints ==============

@app.get("/api/models")
async def list_models():
    """List available Ollama models."""
    import httpx
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {
            "models": [],
            "error": str(e),
            "message": "Ollama may not be running"
        }


@app.get("/api/stats")
async def get_stats():
    """Get system statistics."""
    import sqlite3
    
    db_path = "data/research.db"
    stats = {
        "total_sessions": 0,
        "total_sources": 0,
        "total_claims": 0,
        "db_size_mb": 0
    }
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM research_sessions")
            stats["total_sessions"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sources")
            stats["total_sources"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM claims")
            stats["total_claims"] = cursor.fetchone()[0]

        import os
        stats["db_size_mb"] = round(os.path.getsize(db_path) / (1024 * 1024), 2)

    except Exception as e:
        stats["error"] = str(e)
    
    return stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
