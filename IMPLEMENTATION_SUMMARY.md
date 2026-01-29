# Research OS v1.1 - Implementation Summary

## What Was Built

A complete, production-ready multi-agent research system with cloud LLM support via OpenRouter.

### Backend (Python/FastAPI)

#### Core Components

| Component | File | Description |
|-----------|------|-------------|
| **Database** | `app/db/database.py` | SQLite with vector support, stores sources, claims, sessions |
| **Models** | `app/db/models.py` | Pydantic models for all data types |
| **Search** | `app/core/search.py` | OpenRouter web search (Exa) + DuckDuckGo fallback |
| **Crawler** | `app/core/crawler.py` | Async web crawler (httpx + Playwright) |
| **Curator** | `app/core/curator.py` | Deduplication, credibility scoring, filtering |
| **Knowledge Graph** | `app/core/knowledge_graph.py` | NetworkX graph with D3 export |
| **Verifier** | `app/core/verifier.py` | 3-layer verification (exact, semantic, NLI) |
| **Debate** | `app/core/debate.py` | Multi-round agent debate orchestration |
| **Session** | `app/core/session.py` | Full research pipeline state machine |

#### Agents

| Agent | File | Role | Default Model |
|-------|------|------|---------------|
| **Scout** | `app/agents/specialized.py` | Finds trends, diverse perspectives | `google/gemini-2.5-flash` |
| **Skeptic** | `app/agents/specialized.py` | Identifies biases, contradictions | `deepseek/deepseek-chat-v3.1` |
| **Analyst** | `app/agents/specialized.py` | Extracts structured claims | `qwen/qwen3-max` |
| **Synthesizer** | `app/agents/specialized.py` | Generates final report | `anthropic/claude-opus-4` |
| **Base** | `app/agents/base.py` | LLM provider abstraction, agent orchestrator | - |

#### Configuration

| Component | File | Description |
|-----------|------|-------------|
| **Settings** | `app/core/config.py` | Pydantic-settings for environment config |
| **Planner** | `app/core/planner.py` | Query understanding and decomposition |
| **Environment** | `.env` | API keys and model configuration |

#### API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/research` | POST | Start research (blocking) |
| `/api/sessions` | GET | List sessions |
| `/api/sessions/{id}` | GET | Get session |
| `/api/sessions/{id}/report` | GET | Get report |
| `/api/sessions/{id}/graph` | GET | Get graph data |
| `/api/sessions/{id}/sources` | GET | Get sources |
| `/api/sessions/{id}/claims` | GET | Get claims |
| `/ws/research` | WS | Real-time research streaming |

### Frontend (React/TypeScript)

#### Components

| Component | File | Description |
|-----------|------|-------------|
| **QueryBuilder** | `components/QueryBuilder.tsx` | Query input with mode selection |
| **ProgressTracker** | `components/ProgressTracker.tsx` | Live progress with phase indicators |
| **KnowledgeGraph** | `components/KnowledgeGraph.tsx` | D3.js force-directed graph |
| **SourceCard** | `components/SourceCard.tsx` | Source display with credibility |
| **ClaimCard** | `components/ClaimCard.tsx` | Claim with verification status |
| **DebateView** | `components/DebateView.tsx` | Agent debate display |
| **ReportViewer** | `components/ReportViewer.tsx` | Markdown report with download |

#### Hooks

| Hook | File | Description |
|------|------|-------------|
| **useWebSocket** | `hooks/useWebSocket.ts` | WebSocket connection management |

### Research Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           RESEARCH PIPELINE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. PLANNING (5%)                                                        │
│     └─ Decompose query into sub-queries                                  │
│                                                                          │
│  2. SEARCHING (10%)                                                      │
│     └─ OpenRouter web search (Exa) or DuckDuckGo fallback                │
│                                                                          │
│  3. CRAWLING (20%)                                                       │
│     └─ Async crawl URLs, extract text                                    │
│                                                                          │
│  4. CURATING (30%)                                                       │
│     ├─ Exact deduplication (content hash)                                │
│     ├─ Semantic deduplication (embeddings)                               │
│     ├─ Credibility scoring (domain + content signals)                    │
│     └─ Relevance filtering                                               │
│                                                                          │
│  5. EXTRACTING (45%)                                                     │
│     ├─ Scout agent: trends, diverse perspectives                         │
│     ├─ Skeptic agent: biases, contradictions                             │
│     └─ Analyst agent: structured claims                                  │
│                                                                          │
│  6. BUILDING GRAPH (60%)                                                 │
│     └─ NetworkX graph: claims, entities, sources, relations              │
│                                                                          │
│  7. VERIFYING (70%)                                                      │
│     ├─ Exact match verification                                          │
│     ├─ Semantic similarity verification                                  │
│     └─ NLI verification (optional)                                       │
│                                                                          │
│  8. DEBATING (80%) - Conditional                                         │
│     ├─ Round 1: Agents present positions                                 │
│     ├─ Round 2: Rebuttals                                                │
│     └─ Resolution: Consensus or disagreement                             │
│                                                                          │
│  9. SYNTHESIZING (90%)                                                   │
│     └─ Generate final report with citations                              │
│                                                                          │
│  10. COMPLETE (100%)                                                     │
│      └─ Report available for download                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
research-os/
├── USER_STORIES.md              # User stories and acceptance criteria
├── README.md                    # Installation and usage guide
├── IMPLEMENTATION_SUMMARY.md    # This file
├── backend/
│   ├── .env                     # Environment config (create from .env.example)
│   ├── .env.example             # Environment template
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app with WebSocket
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Base agent + LLM provider abstraction
│   │   │   └── specialized.py   # Scout, Skeptic, Analyst, Synthesizer
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py        # Settings (pydantic-settings)
│   │   │   ├── planner.py       # Query understanding and decomposition
│   │   │   ├── search.py        # Multi-provider search (OpenRouter/DuckDuckGo)
│   │   │   ├── crawler.py       # Async web crawler
│   │   │   ├── curator.py       # Source curation
│   │   │   ├── knowledge_graph.py # NetworkX graph
│   │   │   ├── verifier.py      # Claim verification
│   │   │   ├── debate.py        # Debate orchestration
│   │   │   └── session.py       # Research session manager
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── models.py        # Pydantic models
│   │       └── database.py      # SQLite operations
│   ├── data/                    # SQLite database (created at runtime)
│   ├── requirements.txt         # Python dependencies
│   └── test_components.py       # Component tests
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── types/
        │   └── index.ts           # TypeScript types
        ├── hooks/
        │   └── useWebSocket.ts    # WebSocket hook
        └── components/
            ├── QueryBuilder.tsx
            ├── ProgressTracker.tsx
            ├── KnowledgeGraph.tsx
            ├── SourceCard.tsx
            ├── ClaimCard.tsx
            ├── DebateView.tsx
            └── ReportViewer.tsx
```

## Key Features Implemented

### 1. Multi-Agent System
- ✅ Scout, Skeptic, Analyst, Synthesizer agents
- ✅ Parallel execution
- ✅ Multi-provider support (OpenRouter + Ollama fallback)
- ✅ Per-agent model configuration
- ✅ JSON-structured outputs

### 1.5 Web Search
- ✅ OpenRouter web search with Exa plugin (primary)
- ✅ DuckDuckGo fallback (free)
- ✅ AI-optimized search results

### 2. Knowledge Graph
- ✅ NetworkX-based graph
- ✅ Claims, entities, sources as nodes
- ✅ SUPPORTS/CONTRADICTS/ABOUT edges
- ✅ D3.js force-directed visualization
- ✅ Interactive (click, drag, zoom)

### 3. Verification
- ✅ Exact match verification
- ✅ Semantic similarity (embeddings)
- ✅ NLI verification (optional)
- ✅ Confidence scores
- ✅ Source excerpts

### 4. Debate System
- ✅ Automatic trigger on contradictions
- ✅ Multi-round debate protocol
- ✅ Position statements and rebuttals
- ✅ Consensus detection

### 5. Real-Time Streaming
- ✅ WebSocket connection
- ✅ Live progress updates
- ✅ Source/claim/graph events
- ✅ Debate events

### 6. Source Curation
- ✅ URL deduplication
- ✅ Semantic deduplication
- ✅ Credibility scoring (domain + content)
- ✅ Relevance filtering

### 7. Web Interface
- ✅ Query builder with mode selection
- ✅ Progress tracker with phases
- ✅ Knowledge graph visualization
- ✅ Source/claim cards
- ✅ Debate view
- ✅ Report viewer with download

## Installation

### 1. Setup Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure LLM Provider

**Option A: OpenRouter (Recommended)**
```bash
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

Default model configuration:
| Agent | Model | Purpose |
|-------|-------|---------|
| Scout | `google/gemini-2.5-flash` | Fast, broad search |
| Skeptic | `deepseek/deepseek-chat-v3.1` | Critical reasoning |
| Analyst | `qwen/qwen3-max` | Structured extraction |
| Synthesizer | `anthropic/claude-opus-4` | Final report synthesis |

Web search uses OpenRouter's Exa plugin (~$0.02/search).

**Option B: Ollama (Local/Free)**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# Set LLM_PROVIDER=ollama in .env
```

### 3. Setup Frontend
```bash
cd frontend
npm install
```

### 4. Run
```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

Open http://localhost:5173

## Testing

Run component tests:
```bash
cd backend
python test_components.py
```

## Scaling Considerations

### Current Limits

| Component | 50 sources | 200 sources | 1000 sources |
|-----------|------------|-------------|--------------|
| **Crawling** | ~2 min | ~8 min | ~40 min+ |
| **LLM Context** | Fits in prompt | Needs batching | Needs hierarchical |
| **Memory** | ~100MB | ~400MB | ~2GB+ |
| **Graph Viz** | Clean | Crowded | Unusable |
| **Cost** | ~$1-2 | ~$5-10 | ~$25-50 |

### Bottlenecks at Scale

1. **LLM Context Window**: Current agents process 10-15 sources per prompt. At 1000 sources:
   - Need batch processing (chunks of 10-15)
   - Hierarchical synthesis (summarize batches → merge summaries)
   - RAG-style retrieval (embed sources, retrieve relevant chunks per claim)

2. **Knowledge Graph Visualization**: D3 force-directed graph degrades at 500+ nodes
   - Need auto-clustering of related nodes
   - Hierarchical/tree view option
   - Filter by confidence threshold

3. **Web Crawling**: Rate limiting and timeouts become significant
   - Domain-aware rate limiting
   - Connection pooling
   - Parallel worker pool with backoff

4. **Memory**: Source text storage grows linearly
   - Stream processing instead of loading all
   - Database-backed storage with lazy loading
   - Compress/summarize sources after extraction

### Proposed Architecture for 1000+ Sources

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIERARCHICAL PROCESSING                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. SEARCH & CRAWL (parallel workers)                            │
│     └─ 1000 sources → dedupe → 600 unique                        │
│                                                                  │
│  2. BATCH EXTRACTION (10 batches of 60)                          │
│     └─ Each batch → Scout/Skeptic/Analyst → batch claims         │
│                                                                  │
│  3. CLAIM CLUSTERING                                             │
│     └─ 600 claims → embed → cluster → 50 claim groups            │
│                                                                  │
│  4. HIERARCHICAL GRAPH                                           │
│     └─ Top-level: claim groups                                   │
│     └─ Drill-down: individual claims/sources                     │
│                                                                  │
│  5. SYNTHESIS (on clustered claims)                              │
│     └─ Synthesizer works on 50 claim groups, not 600 claims      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Next Steps / Future Enhancements

### Near-term
1. **Batch Processing**: Process sources in configurable batch sizes
2. **Claim Clustering**: Group similar claims using embeddings
3. **Graph Filtering**: Filter nodes by confidence, type, or cluster
4. **Progress Persistence**: Resume interrupted research sessions

### Medium-term
5. **Medical Mode**: PICO extraction, evidence hierarchy, PubMed integration
6. **PDF Support**: Extract text from uploaded PDFs
7. **RAG Retrieval**: Embedding-based source retrieval for synthesis
8. **Hierarchical Graph**: Zoomable graph with cluster expansion

### Long-term
9. **Custom Prompts**: User-configurable agent prompts
10. **Export Formats**: PDF, Word document export
11. **Session Comparison**: Compare multiple research sessions
12. **Collaborative**: Multi-user research sessions
13. **GPU Acceleration**: Faster local inference

## Performance

| Mode | Sources | Time | RAM |
|------|---------|------|-----|
| Quick | 15 | ~2 min | 16GB |
| Standard | 30 | ~5 min | 16GB |
| Deep | 50 | ~10 min | 32GB |

## Hardware Requirements

- **Minimum**: 16GB RAM, no GPU
- **Recommended**: 32GB RAM
- **Optimal**: 64GB RAM + RTX 4070+

## Cost

- **Free tier**: Uses DuckDuckGo search, Ollama local models
- **OpenRouter**: Estimated ~$0.50-3.00 per research session depending on depth
  - Web search (Exa): ~$0.02/query
  - Gemini 2.5 Flash: ~$0.10/M tokens
  - DeepSeek v3.1: ~$0.14/M tokens
  - Qwen3 Max: ~$0.50/M tokens
  - Claude Opus 4: ~$15/M tokens (synthesis only)

## Version History

| Version | Tag | Description |
|---------|-----|-------------|
| v1.0 | `local-ollama-working` | Local Ollama models, DuckDuckGo search |
| v1.1 | `v1.1-openrouter` | OpenRouter multi-model, Exa web search |

## License

MIT License
