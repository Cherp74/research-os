# Research OS v1.0

A sophisticated local multi-agent research system with knowledge graphs, real-time verification, and agent debates.

![Research OS Screenshot](docs/screenshot.png)

## Features

- **Multi-Agent Swarm**: Scout, Skeptic, and Analyst agents work in parallel
- **Knowledge Graph**: Interactive D3.js visualization of claims, entities, and relationships
- **Real-Time Verification**: Three-layer verification (exact, semantic, NLI)
- **Agent Debate**: Automatic debate when contradictions are detected
- **Source Curation**: Deduplication, credibility scoring, and relevance filtering
- **WebSocket Streaming**: Live progress updates as research progresses
- **Local-First**: Runs entirely on your machine with Ollama

## Architecture

```
User Query → Planning → Search → Crawl → Curate → Extract → Verify → Debate → Synthesize
                ↓         ↓        ↓        ↓        ↓        ↓        ↓         ↓
            Sub-queries  URLs   Content  Sources  Claims  Verified  Resolved  Report
```

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- Ollama (local LLM server)

### 1. Install Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.com/download
```

### 2. Pull Required Models

```bash
ollama pull qwen2.5:7b        # For agent inference
ollama pull nomic-embed-text   # For embeddings
```

Optional (for local synthesis without API):
```bash
ollama pull llama3.1:70b       # Requires 40GB+ RAM
```

### 3. Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Setup Frontend

```bash
cd frontend
npm install
```

### 5. Run the Application

Terminal 1 - Backend:
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Usage

1. **Enter a Research Query**: Be specific for best results
   - Good: "What are the cardiovascular effects of GLP-1 drugs in 2024?"
   - Less good: "Tell me about diabetes"

2. **Select Mode**:
   - **Quick** (~2 min, 15 sources): Fast fact-checking
   - **Standard** (~5 min, 30 sources): General research
   - **Deep** (~10 min, 50 sources): Comprehensive analysis

3. **Watch Real-Time Progress**: See sources discovered, claims extracted, and the knowledge graph grow

4. **Explore Results**:
   - **Overview**: Stats and knowledge graph
   - **Sources**: Individual source cards with credibility scores
   - **Claims**: Extracted claims with verification status
   - **Debate**: Agent arguments when contradictions found
   - **Report**: Final synthesized markdown report

## How It Works

### 1. Planning
Decomposes your query into sub-queries for broader coverage.

### 2. Search & Crawl
- Searches DuckDuckGo (free, no API key)
- Crawls URLs in parallel with httpx
- Extracts clean text using newspaper3k + trafilatura

### 3. Curation
- **Deduplication**: URL normalization + semantic similarity
- **Credibility Scoring**: Domain authority, citations, methodology
- **Relevance Filtering**: Embedding similarity to query

### 4. Multi-Agent Extraction
Three agents analyze sources in parallel:
- **Scout**: Finds trends, diverse perspectives, recent developments
- **Skeptic**: Identifies biases, gaps, contradictions
- **Analyst**: Extracts structured claims with precision

### 5. Knowledge Graph
Builds a graph with:
- **Nodes**: Claims (blue), Entities (green), Sources (gray)
- **Edges**: SUPPORTS (green), CONTRADICTS (red), ABOUT (gray)

### 6. Verification
Three-layer verification:
1. **Exact match**: String containment
2. **Semantic similarity**: Embedding cosine similarity
3. **NLI**: Natural Language Inference (most accurate)

### 7. Debate (Conditional)
Triggers when contradictions detected:
- Round 1: Agents present positions
- Round 2: Rebuttals
- Resolution: Consensus or genuine disagreement

### 8. Synthesis
Generates final report with:
- Executive summary
- Key findings with citations
- Areas of agreement/disagreement
- Evidence quality assessment

## Configuration

### Environment Variables

Create `.env` in `backend/`:

```env
# Optional: Use DeepSeek API for synthesis (faster, no local GPU needed)
DEEPSEEK_API_KEY=your_key_here

# Optional: Use SerpAPI for more search results
SERPAPI_KEY=your_key_here
```

### Model Selection

Edit `backend/app/core/session.py`:

```python
# For faster inference (lower quality)
self.scout = ScoutAgent(model="qwen2.5:7b")

# For better quality (slower)
self.scout = ScoutAgent(model="qwen2.5:14b")

# For synthesis with API
self.synthesizer = SynthesizerAgent(model="deepseek-chat")  # Uses API
```

## API Endpoints

### REST API

- `POST /api/research` - Start research (blocking)
- `GET /api/sessions` - List sessions
- `GET /api/sessions/{id}` - Get session
- `GET /api/sessions/{id}/report` - Get report
- `GET /api/sessions/{id}/graph` - Get graph data
- `GET /api/sessions/{id}/sources` - Get sources
- `GET /api/sessions/{id}/claims` - Get claims

### WebSocket

- `WS /ws/research` - Real-time research streaming

Message format:
```json
{
  "query": "your research question",
  "mode": "standard",
  "target_sources": 30
}
```

## Project Structure

```
research-os/
├── backend/
│   ├── app/
│   │   ├── agents/          # Scout, Skeptic, Analyst, Synthesizer
│   │   ├── core/            # Search, Crawler, Curator, Graph, Verifier
│   │   ├── db/              # SQLite models and database
│   │   ├── main.py          # FastAPI app
│   │   └── ...
│   ├── data/                # SQLite database
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # useWebSocket hook
│   │   ├── types/           # TypeScript types
│   │   └── App.tsx          # Main app
│   └── package.json
└── README.md
```

## Hardware Requirements

| Configuration | RAM | GPU | Performance |
|--------------|-----|-----|-------------|
| Minimum | 16GB | None | ~10 min/research |
| Recommended | 32GB | None | ~5 min/research |
| Optimal | 64GB | RTX 4070+ | ~2 min/research |

## Troubleshooting

### "Ollama connection refused"
Make sure Ollama is running:
```bash
ollama serve
```

### "No module named 'app'"
Run from the `backend` directory:
```bash
cd backend
uvicorn app.main:app --reload
```

### Frontend can't connect to backend
Check the proxy in `frontend/vite.config.ts`:
```typescript
proxy: {
  '/api': 'http://localhost:8000',
  '/ws': { target: 'ws://localhost:8000', ws: true }
}
```

### Slow research
- Use Quick mode for faster results
- Check if Ollama is using GPU: `ollama ps`
- Reduce `target_sources` in the request

## License

MIT License - See LICENSE file

## Contributing

Contributions welcome! Please open an issue or PR.

## Roadmap

- [ ] Medical mode with PICO extraction
- [ ] PDF support
- [ ] Custom agent prompts
- [ ] Export to PDF/Word
- [ ] Session comparison
- [ ] Collaborative research
