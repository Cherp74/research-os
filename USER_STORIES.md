# Research OS - User Stories

## Core User Journey

### Story 1: Basic Research Query
**As a** user interested in a topic  
**I want to** enter a research question and get a comprehensive, cited report  
**So that** I can understand the current state of knowledge on that topic

**Acceptance Criteria:**
- User can enter any text query
- System searches multiple sources in parallel
- User sees real-time progress (sources found, claims extracted, etc.)
- Final report includes inline citations to sources
- Report is downloadable as Markdown

### Story 2: Real-Time Progress Visibility
**As a** user waiting for research  
**I want to** see what's happening in real-time  
**So that** I understand the system is working and can see the evidence being gathered

**Acceptance Criteria:**
- WebSocket connection streams live updates
- Shows current phase (planning/searching/analyzing/synthesizing)
- Displays sources as they're discovered with credibility scores
- Shows knowledge graph growing as claims are extracted
- Visual indicator of agent activity (Scout/Skeptic/Analyst working)

### Story 3: Knowledge Graph Exploration
**As a** user reviewing research  
**I want to** explore the relationships between claims and sources  
**So that** I can understand how evidence connects and where conflicts exist

**Acceptance Criteria:**
- Interactive force-directed graph visualization
- Nodes: claims (blue), entities (green), sources (gray)
- Edges: SUPPORTS (green), CONTRADICTS (red), ABOUT (gray)
- Click node to see details
- Zoom and pan controls

### Story 4: Agent Debate Transparency
**As a** user evaluating controversial topics  
**I want to** see when agents disagree and how they resolve it  
**So that** I understand the confidence level of conclusions

**Acceptance Criteria:**
- Debate triggers automatically when contradictions detected
- Shows each agent's position with supporting evidence
- Displays rebuttals and counter-arguments
- Final synthesis includes confidence scores
- Dissenting views preserved in report

### Story 5: Source Credibility Assessment
**As a** user evaluating information quality  
**I want to** see why sources are ranked as credible or not  
**So that** I can judge the reliability of evidence myself

**Acceptance Criteria:**
- Each source shows credibility score (0-1)
- Score breakdown: domain authority, content signals, recency
- Visual indicator (badge) for high-credibility sources
- Warning flags for low-credibility or biased sources

### Story 6: Claim Verification
**As a** user fact-checking a report  
**I want to** click any claim and see the source text that supports it  
**So that** I can verify claims independently

**Acceptance Criteria:**
- Every claim links to its source(s)
- Hover/click reveals source excerpt
- Verification method shown (exact match/semantic/NLI)
- Confidence score displayed

### Story 7: Research Session Persistence
**As a** user doing multiple research projects  
**I want to** save and resume research sessions  
**So that** I don't lose work and can compare results

**Acceptance Criteria:**
- Sessions saved to local database
- Can view list of past research sessions
- Can reload previous session with all data
- Export session data (graph, sources, report)

### Story 8: Medical Research Mode
**As a** medical professional or researcher  
**I want to** search with medical-specific filters and evidence grading  
**So that** I can find high-quality clinical evidence

**Acceptance Criteria:**
- PICO extraction (Population, Intervention, Comparison, Outcome)
- Evidence hierarchy labels (RCT > Meta-analysis > Cohort)
- PubMed integration
- Risk of bias auto-flagging
- Medical disclaimer on all outputs

## Technical User Stories

### Story 9: Local-First Operation
**As a** privacy-conscious user  
**I want to** run everything locally without cloud dependencies  
**So that** my research queries remain private

**Acceptance Criteria:**
- All LLM inference via local Ollama
- No data sent to external APIs (except optional search)
- Works offline after initial setup
- File-based storage (SQLite, JSON)

### Story 10: Hardware Flexibility
**As a** user with varying hardware  
**I want to** configure the system for my machine's capabilities  
**So that** it runs well whether I have 16GB or 64GB RAM

**Acceptance Criteria:**
- Configurable model sizes (7B/14B/70B)
- Option to use API for synthesis if local GPU insufficient
- Parallel/sequential agent execution toggle
- Memory usage monitoring and warnings

## Epic: End-to-End Research Flow

```
User opens app → Enters query "GLP-1 drugs cardiovascular effects"
    ↓
System shows planning phase → Decomposes into sub-queries
    ↓
Live source discovery → "Found 45 sources... Crawling..."
    ↓
Curation complete → "25 unique, credible sources selected"
    ↓
Agents activate → Scout (finding trends), Skeptic (checking bias), Analyst (extracting claims)
    ↓
Knowledge graph builds → User sees nodes/edges appearing in real-time
    ↓
Contradiction detected → Debate phase begins
    ↓
Synthesis → Final report generated with citations
    ↓
User explores graph, verifies claims, downloads report
```
