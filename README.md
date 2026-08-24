# 🏔️ Ridge · Self-Correcting RAG Intelligence Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_16_·_pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6B6B?style=for-the-badge)
![Groq](https://img.shields.io/badge/LLM_Engine-Groq_LPU-F55036?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React_19_·_Vite_·_React_Router-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Ridge** is an enterprise-grade, multi-tenant Corrective Retrieval-Augmented Generation (CRAG) platform. It transforms raw technical documents, resumes, slide decks, codebases, spreadsheets, and web sources into an audited, hallucination-resistant LangGraph state machine backed by **PostgreSQL as the primary system of record**, **pgvector for dense HNSW retrieval**, native full-text lexical search, SQL Reciprocal Rank Fusion, compound query decomposition, small-to-big parent retrieval, domain glossary indexing, multi-institution workspace isolation, user feedback tracking, document lifecycle management, and real-time observability.

</div>

---

## 🌟 Key Architecture & Capabilities

### 1. 🐘 PostgreSQL + pgvector System of Record & Hybrid Retrieval
* **Central Persistent Data Layer**: Unified relational architecture with normalized tables across tenants, users, documents, chunks, embeddings, conversations, messages, structured citations, retrieval telemetry, feedbacks, and semantic cache.
* **Dense HNSW Vector Search**: Uses pgvector cosine distance (`<=>`) with dedicated HNSW vector indexes on 1024-dimensional embeddings (`BAAI/bge-large-en-v1.5`).
* **Sparse Full-Text Search (FTS)**: Native PostgreSQL GIN indexes on `search_vector` (`tsvector`) executing `plainto_tsquery('english', ...)`.
* **SQL Reciprocal Rank Fusion (RRF)**: Merges dense vector and sparse lexical rankings directly inside PostgreSQL with $K=60$ reciprocal rank weighting before cross-encoder re-ranking.
* **Sub-50ms Retrieval**: Average hybrid retrieval latency of **~40–75 ms** directly from indexed PostgreSQL tables.

---

### 2. 🏛️ Multi-Tenant Enterprise Isolation & Document Sharing
* **Institutional Boundaries**: Strict tenant-scoped data isolation across PostgreSQL tables and pgvector embedding spaces.
* **Public vs Private Knowledge**: Climbers can ingest documents privately or share them with their entire enterprise with a 1-click toggle.
* **Institution Provisioning**: Multi-tier registration allowing institutions to be registered with customized climber quotas and slug codes.

---

### 3. 📊 Dedicated Enterprise Admin Portal (`/admin`)
* **Executive Analytics & System Usage**: Real-time KPI cards (Climbers, Inferences Today, Chunks, Storage Footprint in MB), 7-day query volume trend bar charts, and top active climbers leaderboard.
* **Climber Roster & Quota Management**: Full user roster with multi-select checkboxes, batch account deletion, daily inference quota configuration, and role promotion.
* **Knowledge & Document Management**: Searchable repository of all enterprise documents with file size formatting, chunk counts, sharing status toggle, and batch vector purge.
* **Feedback & Accuracy Inquiry Lifecycle**: Review climber-submitted accuracy reports, bug tickets, and feature requests. Admins can update statuses (`Open`, `In Review`, `Resolved`) and attach resolution notes directly visible to users.
* **Institution Management (SuperAdmin)**: Global multi-tenant administration, capacity progress bars, and workspace suspension/activation.

---

### 4. 💬 User Feedback & Thumbs Down Accuracy Reporting
* **Contextual Response Feedback**: Clicking **Thumbs Down** on any assistant answer provides an inline prompt to report inaccuracies, pre-populating the prompt and response context into the Feedback Modal.
* **Inquiry Status Tracker**: Climbers can view the status of their past inquiries and read administrative responses and resolution notes.

---

### 5. 🔀 Compound Question Decomposition (Multi-Hop CRAG)
* **Automatic Multi-Part Detection**: Identifies complex multi-hop queries (e.g., *"Compare PEAS with DECIDE and also explain BFS"*).
* **Parallel Hybrid Retrieval**: Splits queries into 2–4 focused sub-queries, executes parallel PostgreSQL pgvector + FTS searches, and fuses candidates.
* **Coverage Safety Valve**: If the relevant document count is lower than expected sub-queries, the router automatically triggers web search to fill the missing sub-query gaps.

---

### 6. 🔍 Small-to-Big Retrieval (Parent Section Expansion)
* **High-Precision Indexing**: Indexes compact child chunks (400 chars, 60 overlap) with pgvector embeddings for accurate vector matching.
* **Relational Parent Storage**: Stores full parent sections with metadata in PostgreSQL `document_chunks` with parent section references.
* **Generation-Time Expansion**: Automatically swaps retrieved child chunks for full parent sections with automatic de-duplication before LLM synthesis.

---

### 7. 📖 Corpus-Aware Domain Glossary & Acronym Engine
* **Automated Initialism & Entity Extraction**: Scans ingested documents for domain acronyms and full expansions (e.g. `HNSW`, `PEAS`, `CRAG`, `DSU`) with heuristic prefix-stripping and validation.
* **Dynamic Query Expansion**: Enriches reformulated queries with contextual acronym expansions from the active document corpus during multi-hop retrieval.
* **Relational Synchronization**: Managed in PostgreSQL `glossary_terms` table, automatically pruning orphaned entries when source documents are deleted.

---

### 8. 🧠 Semantic Chunking by Embedding Gradient
* **Embedding Gradient Detector**: Tokenizes document sentences and measures cosine similarity between consecutive sliding windows ($W=3$).
* **Self-Calibrating Percentile Boundaries**: Identifies topic shifts at the bottom 25th percentile of cosine similarity scores, eliminating arbitrary character-count cuts.
* **Coherence Optimizer**: Merges micro-chunks ($<200$ chars) and applies heading inheritance (`ensure_chunk_has_headings`) to maintain document context.

---

### 9. 📁 Source-Scoped Metadata-Filtered Retrieval
* **Scoped Search**: Choose to query across **"All Sources"** or scope strictly to specific indexed documents (e.g. `resume.pdf` or `Ai Module-2.pptx`).
* **Dynamic Toolbar Selector**: Input bar dropdown automatically populated from `/api/kb/sources`.
* **Metadata WHERE Clauses**: Direct SQL filtering on `uploaded_by` and `filename` in PostgreSQL.

---

### 10. ⚡ Semantic Vector Query Cache (pgvector)
* **Vector Sub-Millisecond Short-Circuit**: Hashes and embeds incoming queries; if cosine similarity in PostgreSQL `query_cache` is $\ge 0.96$, returns the answer in $<5\text{ms}$.
* **Persistent Storage**: Verified high-confidence answers ($\text{Score} \ge 60$) are stored asynchronously in PostgreSQL `query_cache`.
* **Visual Telemetry**: Displays `⚡ Semantic Cache Hit` in the real-time ascent timeline.

---

### 11. ⚔️ Document Conflict Detection & Side-by-Side Diff Viewer
* **Contradiction Auditor**: When $\ge 2$ documents contain conflicting policies, dates, or numbers, audits discrepancies and surfaces both perspectives.
* **Interactive Diff Modal**: Clicking **"Compare Sources"** on the amber Conflict Alert Banner opens a side-by-side split comparison modal displaying source cards, text excerpts, and evaluator notes.

---

### 12. 📊 Automated RAG Triad Evaluation Harness
* **Automated Benchmark Suite**: [`eval/evaluate.py`](eval/evaluate.py) benchmarks test cases from [`eval/gold_dataset.json`](eval/gold_dataset.json).
* **RAG Triad Metrics**:
  1. **Context Recall**: % of gold ground-truth concepts present in retrieved documents (**91.7%** on in-domain corpus).
  2. **Faithfulness**: Hallucination auditor verdict (`grounded == 'yes'`).
  3. **Answer Relevance**: Keyword and semantic alignment between synthesized answer and reference.

---

### 13. 🎨 Theme Harmony & Diagram Rendering
* **Synchronized Color Palettes**: *Stone & Summit* (Warm Sandstone light topo), *Chalk & Void* (Dark Basalt & Alpine Teal), and *Rust & Ridge* (Terracotta Crag).
* **Adaptive Mermaid SVG Diagrams**: Detects ````mermaid ... ```` code blocks and dynamically renders SVGs styled to the active palette.
* **KaTeX Mathematical Equations**: Full rendering support for inline `$ ... $` and display block `$$ ... $$` LaTeX equations.

---

## 🏗️ LangGraph State Machine Architecture

```mermaid
flowchart TD
    Start(["User Query"]) --> CacheCheck{"pgvector Semantic Cache Hit?<br/>Sim ≥ 0.96"}
    CacheCheck -->|"Yes (under 5ms)"| FastReturn(["Instant Verified Answer"])
    CacheCheck -->|No| Decompose["Query Decomposition Node<br/>Split Multi-Hop Queries"]
    
    Decompose --> Retrieve["PostgreSQL Hybrid Retrieval Node<br/>pgvector HNSW + FTS + SQL RRF + FlashRank + S2B"]
    Retrieve --> Grade["Relevance Grading Node<br/>Strict LLM Veracity Evaluation"]
    
    Grade -->|"Relevant Docs ≥ 1"| ConflictAudit{"Conflict Check<br/>Distinct Sources ≥ 2"}
    ConflictAudit -->|Yes| FlagConflict["Audit Contradictions & Extract Passages"]
    ConflictAudit -->|No| Generate["Answer Synthesis Node<br/>Groq LPU + Fail-Safe"]
    FlagConflict --> Generate
    
    Grade -->|"0 Relevant Docs"| RouteCheck{"Loops < Max Loops?"}
    RouteCheck -->|Yes| Rewrite["Query Reformulation Node<br/>Glossary Acronym Enrichment"]
    Rewrite --> Retrieve
    RouteCheck -->|"No / Web Search"| WebSearch["Web Search Fallback Node<br/>DDGS 5s Timeout"]
    WebSearch --> Generate
    
    Generate --> HallucinationAudit["Hallucination Auditor Node<br/>Faithfulness Verification"]
    HallucinationAudit --> CacheStore["Store in PostgreSQL pgvector Cache"]
    CacheStore --> End(["Stream Verified SSE Response"])
```

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.11+
* Node.js 18+ and npm
* Docker (for PostgreSQL + pgvector)
* A free [Groq API Key](https://console.groq.com/)

### 2. Start PostgreSQL + pgvector Database
```bash
# Start local PostgreSQL with pgvector extension on port 5433
docker compose up -d postgres
```

### 3. Backend Setup
```bash
# Clone the repository
git clone https://github.com/KARTHIKKJ369/Ridge.git
cd Ridge

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and insert your GROQ_API_KEY

# Initialize or verify PostgreSQL schema
uv run python -c "import asyncio; from app.db.database import init_db; asyncio.run(init_db())"
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run build
cd ..
```

### 5. Running Locally
```bash
# Start backend API (FastAPI + LangGraph + PostgreSQL)
uvicorn api:app --reload --port 8000

# In a second terminal, start Vite frontend dev server (optional for hot reload)
cd frontend
npm run dev
```
Open **`http://localhost:5173`** (or `http://localhost:8000` for the production bundle).

---

## 🧪 Benchmarking & Diagnostics

### Run Retrieval-Only Benchmark (pgvector Hybrid Latency & Alignment)
```bash
python scripts/benchmark_retrieval.py
```

### Run Full RAG Triad Evaluation Suite
```bash
python eval/evaluate.py
```

### Run Full Pytest Test Suite
```bash
uv run pytest -v
```

---

## ⚙️ Environment Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `GROQ_API_KEY` | **Required**: Groq Cloud API Key | — |
| `GROQ_MODEL` | Primary synthesis model | `openai/gpt-oss-120b` |
| `GROQ_FAST_MODEL` | Ultra-fast model for grading & decomposition | `openai/gpt-oss-20b` |
| `DATABASE_URL` | PostgreSQL asyncpg connection string | `postgresql+asyncpg://ridge:ridge@localhost:5433/ridge` |
| `DATABASE_URL_SYNC` | PostgreSQL sync connection string | `postgresql://ridge:ridge@localhost:5433/ridge` |
| `EMBEDDING_MODEL` | Local HuggingFace sentence transformer | `BAAI/bge-large-en-v1.5` |
| `EMBEDDING_DIMENSION`| Vector embedding dimension | `1024` |
| `RETRIEVAL_BACKEND` | Active retrieval engine | `pgvector` |
| `RETRIEVER_K` | Top documents to keep after FlashRank re-ranking | `4` |
| `RETRIEVER_FETCH_K` | Candidate chunks fetched per retrieval call | `25` |
| `RERANK_MODEL` | FlashRank re-ranking cross-encoder model | `ms-marco-MiniLM-L-12-v2` |
| `MAX_REWRITE_LOOPS` | Max query reformulation attempts | `1` |
| `AUTH_ENABLED` | Toggle user authentication and tenant isolation | `true` |
| `JWT_SECRET` | Secret key for signed JWT session tokens | Generated 32-byte hex |

---

## 📁 Repository Structure

```
Ridge/
├── main.py                # Core LangGraph state machine & CRAG pipeline
├── api.py                 # FastAPI backend & SSE streaming endpoints
├── auth.py                # JWT authentication, RBAC & multi-tenancy
├── rag_ingest.py          # Document parsers, OCR, & semantic gradient chunking
├── parent_store.py        # Small-to-Big parent section store
├── query_cache.py         # Vector query cache helper
├── glossary.py            # Domain acronym & entity glossary engine
├── requirements.txt       # Python backend dependencies
├── pyproject.toml         # Project metadata & dependencies
├── app/
│   ├── db/                # PostgreSQL + pgvector data architecture
│   │   ├── database.py    # Async engine & session factories
│   │   ├── models/        # SQLAlchemy ORM models (Tenant, User, Document, Feedback, etc.)
│   │   └── repositories/  # Isolated data access repositories (feedback_repo, tenant_repo, doc_repo)
│   └── retrieval/         # Unified hybrid retrieval engines
│       ├── interface.py   # BaseRetriever & RetrievalCandidate
│       ├── pgvector_retriever.py # Dense HNSW + FTS + SQL RRF
│       └── hybrid.py      # Unified hybrid retriever orchestrator
├── eval/
│   ├── evaluate.py        # Automated RAG Triad evaluation harness
│   ├── gold_dataset.json  # Benchmark ground-truth test cases
│   └── benchmark_report.md# Latest benchmark run scorecard
├── tests/                 # Full automated test suite
│   ├── test_db_foundation.py
│   ├── test_conversations_api.py
│   ├── test_multi_tenant_isolation.py
│   └── test_retrieval_engines.py
├── scripts/               # Migration, benchmarking & test utilities
└── frontend/              # Alpine 2026 React 19 + TypeScript + Vite UI
    ├── src/
    │   ├── App.tsx        # Main application component & state machine
    │   ├── App.css        # Design system tokens & CSS styling
    │   ├── pages/         # Admin Dashboard dedicated full-page router
    │   └── components/    # FeedbackModal, AuthModal, and auxiliary UI components
    └── package.json       # Frontend npm dependencies
```

---

## 📄 License
MIT License. Built with ❤️ for enterprise-grade, hallucination-resistant research.
