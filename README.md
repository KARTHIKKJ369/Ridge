# 🏔️ Ridge · Self-Correcting RAG Intelligence Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_16_·_pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6B6B?style=for-the-badge)
![LLM Engines](https://img.shields.io/badge/LLM_Engines-Groq_LPU_·_Google_Gemini-F55036?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React_19_·_Vite_·_TypeScript-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/Tests-30%2F30_Passing-brightgreen?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Ridge** is an industrial-grade, multi-tenant Corrective Retrieval-Augmented Generation (CRAG) platform. It transforms complex technical documents, financial 10-Ks, slide decks, spreadsheets, codebases, and web sources into an audited, hallucination-resistant LangGraph state machine backed by **PostgreSQL as the primary system of record**, **pgvector for dense HNSW retrieval**, native full-text lexical search, SQL Reciprocal Rank Fusion, layout-aware AST document intelligence, Anthropic-style contextual retrieval, sub-second multi-LLM orchestration (Groq LPU + Google Gemini), and real-time observability.

</div>

---

## 🌟 Key Architecture & Capabilities

```mermaid
flowchart TD
    Doc[Source Document] --> Parsers[Unified Document Parser<br/>PDF, DOCX, PPTX, XLSX, MD, Web]
    Parsers --> AST[Document AST Hierarchy<br/>Pages, Blocks, Tables, Figures]
    AST --> Extraction[Table & Figure Extraction<br/>Markdown Tables & OCR Schemas]
    Extraction --> Chunker[Structure-Aware Semantic Chunker<br/>Atomic Tables & Code Syntax Blocks]
    Chunker --> Dedup[Deduplication & Boilerplate Stripper<br/>SHA-256 + 64-bit SimHash]
    Dedup --> Contextual[Anthropic Contextual Enricher<br/>Situated 50-100 Token Breadcrumbs]
    Contextual --> Summaries[Hierarchical Document Summarizer<br/>Executive Document Summaries]
    Summaries --> PG[(PostgreSQL System of Record<br/>pgvector HNSW + GIN FTS)]

    Query[User Query] --> Router[Query Intent Router<br/>Exact, Tabular, Semantic, Summary, Multi-Hop]
    Router --> Hybrid[Hybrid Vector + GIN FTS Search + RRF]
    Hybrid --> Reranker[FlashRank Neural Cross-Encoder]
    Reranker --> Packer[Bounded Parent & Neighbor Context Packer<br/>Deduplicated Context Budgeting]
    Packer --> Synthesis[LangGraph Answer Synthesis<br/>Clean Citations & Zero Search Bleed]
```

---

### 1. 📑 Unified Document AST & Multi-Format Parsing
* **Normalized Document Hierarchy**: Ingested sources are parsed into a normalized `DocumentAST` $\rightarrow$ `PageAST` $\rightarrow$ `BlockAST` (`HEADING`, `PARAGRAPH`, `TABLE`, `FIGURE`, `CODE`, `LIST`).
* **Multi-Format Parsers**:
  * **PDF Structure Parser**: Multi-column reading order reconstruction + RapidOCR fallback for scanned pages.
  * **Office Document Parser**: Native structure extraction for `.docx`, `.pptx` slides, `.xlsx` workbooks, and `.csv`/`.tsv`.
  * **Markdown & Web Parser**: Preserves heading chains, code fences, and article HTML content while stripping navigation boilerplate.

---

### 2. 📊 Layout-Aware Table & Multimodal Figure Extraction
* **Atomic Markdown Tables**: Tables are extracted as complete Markdown representations with replicated headers and structured JSON, persisted to PostgreSQL `document_tables`.
* **Visual Figure Records**: Captures captions, visual descriptions, and embedded OCR text, persisted to PostgreSQL `document_figures`.
* **Dual Representation**:
  * `raw_content`: Clean, unpolluted text used for LLM generation and citations.
  * `contextual_content`: Situated context used for dense vector and lexical FTS indexing.

---

### 3. 🧩 Structure-Aware Semantic Chunking
* **Semantic Boundary Chunking**: Eliminates arbitrary character cuts:
  * **Tables**: Preserved as atomic Markdown blocks with preserved column schemas.
  * **Code**: Preserved as intact syntax blocks with language identifiers.
  * **Figures**: Preserved as multimodal visual chunks with captions + OCR.
  * **Paragraphs**: Sentence-bounded chunking with inherited document heading chains (`[Context: Doc > Chapter > Section]`).

---

### 4. 🧠 Anthropic-Style Contextual Retrieval
* **Situated Chunk Context**: Automatically prepends 50–100 token document-level context to retrievable chunks prior to vector embedding and FTS indexing.
* **Deterministic Fallback**: Generates structured hierarchy breadcrumbs when offline or LLM contextualization is disabled.
* **Zero Citation Pollution**: Keeps generated answers and citations clean by indexing `contextual_content` while preserving `raw_content` for prompt assembly.

---

### 5. 🔍 Bounded Parent & Neighbor Context Packing
* **Small-to-Big Parent Expansion**: Resolves high-precision child search hits to complete structured parent sections.
* **Deduplication & Passage Merging**: Merges multiple matching child chunks from the same parent section into a single contiguous passage, eliminating redundant text.
* **Bounded Context Budgeting**: Enforces strict passage limits (`1,800 chars`) and total context limits (`5,000 chars`) to maximize LLM attention density.

---

### 6. 🧹 Exact & Near-Duplicate Deduplication & Boilerplate Stripping
* **Exact Deduplication (SHA-256)**: Normalized content hashing suppresses identical duplicate chunks across multi-page uploads.
* **Near-Duplicate Detection (SimHash)**: 64-bit SimHash fingerprinting and Hamming distance calculations link near-duplicate passages.
* **Boilerplate Detection**: Pattern matching and frequency analysis filters out recurring headers, footers, `Page X of Y` markers, and confidential/copyright watermarks.
* **Lineage Tracking**: Records `dedup_removed_count` in PostgreSQL `ingestion_runs`.

---

### 7. 🧭 Query-Aware Retrieval Intent Routing
* **Sub-Millisecond Archetype Classification**:
  * `EXACT / LOOKUP`: Acronyms, identifiers $\rightarrow$ dense vector + heavy sparse FTS + domain glossary lookup.
  * `TABULAR / NUMERIC`: Quantitative metrics $\rightarrow$ priority matching on `document_tables` and Markdown tables.
  * `CONCEPTUAL / SEMANTIC`: Explanatory questions $\rightarrow$ balanced hybrid dense vector + RRF + parent expansion.
  * `SUMMARIZATION / GLOBAL`: Overview queries $\rightarrow$ executive summary chunk priority.
  * `MULTI-HOP / COMPARISON`: Comparative analysis $\rightarrow$ multi-source retrieval and bounded context packing.

---

### 8. 🐘 PostgreSQL + pgvector System of Record & Hybrid Retrieval
* **Central Persistent Data Layer**: Unified relational architecture with normalized tables across tenants, users, documents, chunks, tables, figures, embeddings, conversations, messages, structured citations, retrieval telemetry, feedbacks, and semantic cache.
* **Dense HNSW Vector Search**: Uses pgvector cosine distance (`<=>`) with dedicated HNSW vector indexes on 1024-dimensional embeddings (`BAAI/bge-large-en-v1.5`).
* **Sparse Full-Text Search (FTS)**: Native PostgreSQL GIN indexes on `search_vector` (`tsvector`) executing `plainto_tsquery('english', ...)`.
* **SQL Reciprocal Rank Fusion (RRF)**: Merges dense vector and sparse lexical rankings directly inside PostgreSQL with $K=60$ reciprocal rank weighting before cross-encoder re-ranking.
* **Sub-90ms Retrieval**: Average hybrid retrieval latency of **~75–90 ms** directly from indexed PostgreSQL tables.

---

### 9. ⚡ Multi-Provider LLM Engine & Sub-Second Execution
* **Groq LPU Engine (Default)**:
  * **Generation Tier**: `openai/gpt-oss-120b` (Flagship 120B parameter model delivering sub-second grounded answers at 400+ tokens/sec).
  * **Auxiliary & Fast Tier**: `openai/gpt-oss-20b` (Sub-300ms evaluation for grading, decomposition, rewriting, and hallucination audits).
* **Google Gemini 3.5 & 3.7 Tier**:
  * **Generation**: `gemini-3.5-flash` with automatic failover to `gemini-3.5-flash-lite` (15 RPM tier) on rate limits.
  * **Fast Auxiliary**: `gemini-3.5-flash-lite` for high-frequency pipeline operations.
* **Zero Prompt Bleed**: Structured `SystemMessage` and `HumanMessage` isolation ensures system rules never leak into generated answers.

---

### 10. 🏛️ Multi-Tenant Enterprise Isolation & Document Sharing
* **Institutional Boundaries**: Strict tenant-scoped data isolation across PostgreSQL tables and pgvector embedding spaces.
* **Role-Based Access Control (RBAC)**: Supports `superadmin`, `admin`, `climber`, and `guest` roles with cascading tenant and user deletion.
* **Public vs Private Knowledge**: Users can ingest documents privately or share them with their entire enterprise with a 1-click toggle.
* **Batch Operations**: Multi-select management for users, institutions, and documents with instant vector store synchronization.

---

### 11. 📊 Dedicated Enterprise Admin Portal (`/admin`)
* **Executive Analytics & System Usage**: Real-time KPI cards (Climbers, Inferences Today, Chunks, Storage Footprint in MB), query volume trend charts, and active climbers leaderboard.
* **Roster & Quota Management**: Full user roster with multi-select checkboxes, batch account deletion, daily inference quota configuration, and role promotion.
* **Institution Management**: Multi-select batch institution deletion with automatic cascade cleanup of all associated users and documents.
* **Feedback & Accuracy Inquiry Lifecycle**: Review user-submitted accuracy reports, bug tickets, and feature requests with status tracking (`Open`, `In Review`, `Resolved`).

---

### 12. ⚡ Semantic Vector Query Cache (pgvector)
* **Vector Sub-Millisecond Short-Circuit**: Hashes and embeds incoming queries; if cosine similarity in PostgreSQL `query_cache` is $\ge 0.96$, returns the answer in $<5\text{ms}$.
* **Persistent Storage**: Verified high-confidence answers are stored asynchronously in PostgreSQL `query_cache`.

---

## 🏗️ LangGraph State Machine Architecture

```mermaid
flowchart TD
    Start(["User Query"]) --> CacheCheck{"pgvector Semantic Cache Hit?<br/>Sim ≥ 0.96"}
    CacheCheck -->|"Yes (under 5ms)"| FastReturn(["Instant Verified Answer"])
    CacheCheck -->|No| RouteIntent["Query Intent Router Node<br/>Classify Archetype & Weights"]
    
    RouteIntent --> Decompose["Query Decomposition Node<br/>Split Multi-Hop Queries"]
    Decompose --> Retrieve["PostgreSQL Hybrid Retrieval Node<br/>pgvector HNSW + FTS + SQL RRF + FlashRank + S2B"]
    Retrieve --> Grade["Relevance Grading Node<br/>Strict LLM Veracity Evaluation"]
    
    Grade -->|"Relevant Docs ≥ 1"| ConflictAudit{"Conflict Check<br/>Distinct Sources ≥ 2"}
    ConflictAudit -->|Yes| FlagConflict["Audit Contradictions & Extract Passages"]
    ConflictAudit -->|No| Generate["Answer Synthesis Node<br/>Groq LPU / Gemini"]
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
* A free [Groq API Key](https://console.groq.com/) or [Google AI Studio API Key](https://aistudio.google.com/app/apikey)

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
# Edit .env and insert your GROQ_API_KEY or GOOGLE_API_KEY

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
uv run uvicorn api:app --reload --port 8000

# In a second terminal, start Vite frontend dev server (optional for hot reload)
cd frontend
npm run dev
```
Open **`http://localhost:5173`** (or `http://localhost:8000` for the production bundle).

---

## 🧪 Benchmarking & Diagnostics

### Run Full Pytest Regression Suite (30/30 Passing)
```bash
uv run pytest -v
```

### Run Retrieval Benchmark (pgvector Hybrid Latency & Match Precision)
```bash
python scripts/benchmark_retrieval.py
```

### Run Full RAG Triad Evaluation Suite
```bash
python eval/evaluate.py
```

---

## ⚙️ Environment Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | Active LLM backend (`groq` or `gemini`) | `groq` |
| `GROQ_API_KEY` | Groq Cloud API Key | — |
| `GROQ_MODEL` | Primary synthesis model on Groq | `openai/gpt-oss-120b` |
| `GROQ_FAST_MODEL` | Ultra-fast model for grading & contextualization | `openai/gpt-oss-20b` |
| `GOOGLE_API_KEY` | Google AI Studio API Key | — |
| `GEMINI_MODEL` | Primary synthesis model on Google | `gemini-3.5-flash` |
| `GEMINI_FAST_MODEL` | Fast auxiliary model on Google | `gemini-3.5-flash-lite` |
| `DATABASE_URL` | PostgreSQL asyncpg connection string | `postgresql+asyncpg://ridge:ridge@localhost:5433/ridge` |
| `DATABASE_URL_SYNC` | PostgreSQL sync connection string | `postgresql://ridge:ridge@localhost:5433/ridge` |
| `EMBEDDING_MODEL` | Local HuggingFace sentence transformer | `BAAI/bge-large-en-v1.5` |
| `EMBEDDING_DIMENSION`| Vector embedding dimension | `1024` |
| `ENABLE_CONTEXTUAL_RETRIEVAL` | Toggle Anthropic-style situated chunk context | `true` |
| `ENABLE_HIERARCHICAL_SUMMARIES` | Toggle document executive summary indexing | `true` |
| `RETRIEVAL_BACKEND` | Active retrieval engine | `pgvector` |
| `RETRIEVER_K` | Top documents to keep after FlashRank re-ranking | `6` |
| `RETRIEVER_FETCH_K` | Candidate chunks fetched per retrieval call | `60` |
| `RERANK_MODEL` | FlashRank re-ranking cross-encoder model | `ms-marco-MiniLM-L-12-v2` |
| `MAX_REWRITE_LOOPS` | Max query reformulation attempts | `1` |
| `AUTH_ENABLED` | Toggle user authentication and tenant isolation | `true` |
| `JWT_SECRET` | Secret key for signed JWT session tokens | Generated 32-byte hex |

---

## 📁 Repository Structure

```
Ridge/
├── main.py                     # Core LangGraph state machine & CRAG pipeline
├── api.py                      # FastAPI backend & SSE streaming endpoints
├── auth.py                     # JWT authentication, RBAC & multi-tenancy
├── rag_ingest.py               # Structure-aware document ingestion orchestrator
├── requirements.txt            # Python backend dependencies
├── pyproject.toml              # Project metadata & dependencies
├── app/
│   ├── api/                    # Modular FastAPI REST & SSE routers
│   ├── db/                     # PostgreSQL + pgvector data architecture
│   │   ├── database.py         # Async engine, session factories & idempotent migrations
│   │   ├── models/             # SQLAlchemy ORM models (Tenant, User, Document, Chunk, Table, Figure, IngestionRun)
│   │   └── repositories/       # Data access repositories (tenant, user, doc, feedback, glossary)
│   ├── document_intelligence/  # Structure-Aware Document Intelligence Engine
│   │   ├── ast.py              # Unified DocumentAST, PageAST, BlockAST, TableBlock, FigureBlock
│   │   ├── parser.py           # Multi-format structure parsers (PDF, DOCX, PPTX, XLSX, MD, Web)
│   │   ├── chunker.py          # StructureAwareChunker (atomic tables, code blocks, figures)
│   │   ├── dedup.py            # SHA-256 + 64-bit SimHash Deduplicator & Boilerplate Stripper
│   │   └── summarizer.py       # Hierarchical Document & Section Summarizer
│   ├── graph/                  # LangGraph CRAG nodes, state, prompts & LLM factory
│   │   ├── builder.py          # Graph compilation & dynamic conditional routing
│   │   ├── llm_factory.py      # Unified Groq LPU & Google Gemini multi-tier factory
│   │   ├── prompts.py          # Structured system prompts & output cleaners
│   │   └── nodes/              # Individual pipeline node implementations
│   └── retrieval/              # Industrial-grade hybrid retrieval engine
│       ├── interface.py        # BaseRetriever & RetrievalCandidate
│       ├── pgvector_retriever.py # Dense HNSW + FTS + SQL RRF
│       ├── hybrid.py           # Unified hybrid retriever orchestrator
│       ├── contextual.py       # Anthropic-style Contextual Retrieval Engine
│       ├── context_packer.py   # Bounded Parent & Neighbor Context Packer
│       └── router.py           # Query-Aware Retrieval Intent Router
├── eval/
│   ├── evaluate.py             # Automated RAG Triad evaluation harness
│   ├── gold_dataset.json       # Benchmark ground-truth test cases
│   └── benchmark_report.md     # Latest benchmark run scorecard
├── tests/                      # Full automated test suite (30/30 passing)
│   ├── test_db_foundation.py
│   ├── test_conversations_api.py
│   ├── test_multi_tenant_isolation.py
│   ├── test_retrieval_engines.py
│   └── test_document_intelligence.py
├── scripts/                    # Migration, benchmarking & test utilities
└── frontend/                   # React 19 + TypeScript + Vite UI
    ├── src/
    │   ├── App.tsx             # Main application component & state machine
    │   ├── App.css             # Design system tokens & CSS styling
    │   ├── pages/              # Admin Dashboard dedicated full-page router
    │   └── components/         # Modals, Visualizer, Waterfall, and Chat UI
    └── package.json            # Frontend npm dependencies
```

---

## 📄 License
MIT License. Built with ❤️ for enterprise-grade, hallucination-resistant research.

