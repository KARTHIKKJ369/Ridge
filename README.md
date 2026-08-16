---
title: Recall CRAG
emoji: 🔁
colorFrom: red
colorTo: gray
sdk: docker
pinned: false
app_port: 7860
---

# Recall

**Recall** is a Corrective RAG (CRAG) chat application. Ingest your own documents (PDF, Markdown, or plain text) and query them through a LangGraph pipeline that retrieves, grades, rewrites, and generates answers grounded only in your knowledge base.

> **Live on Hugging Face Spaces** — add your `GROQ_API_KEY` as a Space Secret to activate.

## Features

- **Corrective RAG** — LangGraph workflow: retrieve → grade → rewrite/web-search → generate
- **Re-ranking** — FlashRank cross-encoder re-ranks retrieved chunks before grading
- **Smart grading** — Groq LLM grades each chunk and filters irrelevant context
- **Pipeline view** — Live trace panel shows every node, its decision, and latency
- **Source citations** — Each response shows which chunks were used/filtered, with filename and grader rationale
- **Dynamic suggestions** — LLM generates 3 suggested questions after ingestion
- **Beautiful UI** — Dark OKLCH design system, animated hero, toast notifications

## Architecture

```
User query
    ↓
[Retrieve] → ChromaDB MMR search + FlashRank re-ranking
    ↓
[Grade]    → Groq LLM scores each chunk (yes/no + rationale)
    ↓
  relevant?
  ├── yes → [Generate] → Groq LLM answers using only graded context
  └── no  → [Rewrite]  → reformulate query and retry (up to 3 loops)
              or [Web Search] → DuckDuckGo fallback
```

## Configuration (Space Secrets)

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | ✅ | LLM for grading, generation, and suggestions |
| `GROQ_MODEL` | optional | Model name (default: `llama-3.3-70b-versatile`) |
| `EMBEDDING_MODEL` | optional | HF embedding model (default: `sentence-transformers/all-MiniLM-L6-v2`) |
| `RETRIEVER_K` | optional | Chunks kept after re-ranking (default: `5`) |
| `MAX_REWRITE_LOOPS` | optional | Max query rewrite attempts (default: `3`) |

## Local Development

```bash
git clone https://github.com/KARTHIKKJ369/corrective-rag-langgraph
cd corrective-rag-langgraph
cp .env.example .env   # fill in GROQ_API_KEY
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn api:app --reload --port 8000
```

## Tech Stack

- **Backend**: FastAPI · LangGraph · LangChain · ChromaDB · FlashRank · Groq
- **Frontend**: Vite · React · TypeScript
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API key needed)
