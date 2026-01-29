# Research OS - Quick Start Guide

## What You Have

A complete, production-ready multi-agent research system with:

- **3 Specialized Agents**: Scout (trends), Skeptic (bias detection), Analyst (structured extraction)
- **Knowledge Graph**: Interactive D3.js visualization of claims, entities, and relationships
- **Real-Time Verification**: 3-layer verification (exact, semantic, NLI)
- **Agent Debate**: Automatic debate when contradictions are detected
- **WebSocket Streaming**: Live progress updates as research happens
- **Modern UI**: React + TypeScript + Tailwind + D3.js

## File Structure

```
research-os/
├── USER_STORIES.md          # User stories & acceptance criteria
├── README.md                # Full documentation
├── IMPLEMENTATION_SUMMARY.md # Technical implementation details
├── QUICKSTART.md           # This file
├── start.sh                # One-command startup script ⭐
├── backend/
│   ├── app/
│   │   ├── agents/         # Scout, Skeptic, Analyst, Synthesizer
│   │   ├── core/           # Search, Crawler, Curator, Graph, Verifier
│   │   ├── db/             # SQLite database
│   │   └── main.py         # FastAPI app
│   ├── requirements.txt
│   └── test_components.py  # Component tests
└── frontend/
    └── src/
        ├── components/     # React components
        ├── hooks/          # useWebSocket
        └── types/          # TypeScript types
```

## Prerequisites

1. **Python 3.9+**
2. **Node.js 18+**
3. **Ollama** (local LLM server)

## Installation (One Command)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull required models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# 3. Start the application
./start.sh
```

The `start.sh` script will:
- Check Ollama is running
- Pull required models if missing
- Set up Python virtual environment
- Install dependencies
- Start both backend and frontend

## Manual Installation

If you prefer manual setup:

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Open http://localhost:5173
2. Enter a research query (e.g., "What are the cardiovascular effects of GLP-1 drugs?")
3. Select mode (Quick/Standard/Deep)
4. Click "Start Research"
5. Watch real-time progress:
   - Sources being discovered
   - Claims being extracted
   - Knowledge graph growing
   - Agents debating contradictions
6. Explore results in tabs:
   - **Overview**: Stats and knowledge graph
   - **Sources**: Individual sources with credibility scores
   - **Claims**: Extracted claims with verification status
   - **Debate**: Agent arguments (if contradictions found)
   - **Report**: Final markdown report

## API Endpoints

- `GET /` - Health check
- `POST /api/research` - Start research
- `GET /api/sessions` - List sessions
- `GET /api/sessions/{id}` - Get session
- `GET /api/sessions/{id}/report` - Get report
- `GET /api/sessions/{id}/graph` - Get graph data
- `WS /ws/research` - Real-time streaming

## Testing

```bash
cd backend
python test_components.py
```

## Troubleshooting

### "Ollama connection refused"
```bash
ollama serve
```

### "No module named 'app'"
Make sure you're in the `backend` directory when running uvicorn.

### Frontend can't connect to backend
Check `frontend/vite.config.ts` proxy settings.

### Slow research
- Use Quick mode (15 sources)
- Check Ollama GPU usage: `ollama ps`
- Reduce target_sources

## Key Files to Customize

| File | What to Change |
|------|----------------|
| `backend/app/core/session.py` | Model selection, source limits |
| `backend/app/agents/specialized.py` | Agent prompts |
| `frontend/src/components/QueryBuilder.tsx` | UI modes |

## Performance

| Mode | Sources | Time | RAM |
|------|---------|------|-----|
| Quick | 15 | ~2 min | 16GB |
| Standard | 30 | ~5 min | 16GB |
| Deep | 50 | ~10 min | 32GB |

## Architecture

```
Query → Planning → Search → Crawl → Curate → Extract → Verify → Debate → Synthesize
          ↓         ↓        ↓        ↓        ↓        ↓        ↓         ↓
      Sub-queries  URLs   Content  Sources  Claims  Verified  Resolved  Report
```

## What's Next?

1. **Test it**: Run `./start.sh` and try a query
2. **Customize**: Modify agent prompts in `specialized.py`
3. **Enhance**: Add medical mode, PDF support, export formats
4. **Deploy**: Docker, cloud, or keep local

## Support

- Check `README.md` for full documentation
- Check `IMPLEMENTATION_SUMMARY.md` for technical details
- Run `python test_components.py` to verify components

---

**Ready to start?** Just run `./start.sh` 🚀
