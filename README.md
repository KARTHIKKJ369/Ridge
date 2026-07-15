# Recall

Local retrieval-augmented generation (RAG) playground for Lilian Weng's "LLM Powered Autonomous Agents" article.

It ingests content into a local Chroma vector store, retrieves relevant chunks with MMR search, grades them with a LangGraph loop, and asks an Ollama-hosted chat model to answer using only the retrieved context.

> [!NOTE]
> This repository is intentionally small and local-first. It is best suited for experimenting with ingestion, chunking, retrieval, and answer generation rather than serving as a production app.

## What's included

- Header-aware ingestion for web pages, PDFs, Markdown, and text files.
- A rebuild script that recreates the local Chroma database from scratch.
- A LangGraph workflow that retrieves, grades, rewrites, and generates answers.
- Utilities for inspecting chunking behavior and testing older OpenRouter experiments.

## How it works

1. `retriver.py` loads one or more sources and rebuilds `chroma_db/`.
2. `rag_ingest.py` parses each source, preserves headings where possible, and splits long sections into chunks.
3. `main.py` runs a graph with three core stages:
   - retrieve documents
   - grade relevance
   - rewrite the query or generate the final answer
4. `main.py` sends the final context to Ollama and prints the response in the terminal.

## Project layout

- `main.py` - main RAG workflow and CLI entry point.
- `retriver.py` - vector store rebuild script and retrieval sanity check.
- `rag_ingest.py` - shared source loading and chunking helpers.
- `ingest.py` - chunk inspection helper without writing Chroma.
- `debug_openrouter.py` - quick OpenRouter connectivity check.
- `agent.py` - older LangGraph/OpenRouter prototype kept for reference.

## Prerequisites

- Python 3.13 or newer.
- A virtual environment.
- Ollama running locally if you want to use the default answer path.
- Network access the first time you ingest the sample article or download embedding/model weights.

> [!TIP]
> The default configuration points Ollama at `http://localhost:11434` and uses `gemma4:12b` for generation. You can override both in `.env`.

## Setup

Create and activate the virtual environment, then install dependencies:

```bash
python -m venv recall-env
source recall-env/bin/activate
pip install -r requirements.txt
```

Optional: copy the example environment file if you want to override settings or use the OpenRouter debug scripts.

```bash
cp .env.example .env
```

## Configuration

The main runtime settings are read from environment variables. The most useful ones are:

| Variable | Purpose | Default |
| --- | --- | --- |
| `ARTICLE_URL` | Source article used by the default ingest script | `https://lilianweng.github.io/posts/2023-06-23-agent/` |
| `CHROMA_DIR` | Location of the local vector store | `./chroma_db` |
| `EMBEDDING_MODEL` | Hugging Face embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Fallback model used when specific grade/generate models are unset | `gemma4:12b` |
| `OLLAMA_GRADE_MODEL` | Smaller model used for relevance grading | inherits `OLLAMA_MODEL` |
| `OLLAMA_GENERATE_MODEL` | Model used for the final answer | inherits `OLLAMA_MODEL` |
| `RETRIEVER_K` | Number of documents kept after retrieval | `5` |
| `RETRIEVER_FETCH_K` | Number of candidates fetched before MMR selection | `15` |
| `RETRIEVER_LAMBDA_MULT` | MMR diversity trade-off | `0.5` |
| `MAX_REWRITE_LOOPS` | Safety limit for query rewriting | `3` |

## Usage

Rebuild the local vector database:

```bash
source recall-env/bin/activate
python retriver.py
```

You can also provide your own sources. URLs, `.pdf`, `.md`, and `.txt` files are supported.

```bash
python retriver.py https://example.com/post ./notes.md ./paper.pdf
```

Run the main RAG workflow:

```bash
python main.py
```

Ask a custom question:

```bash
python main.py "What is task decomposition in LLM agents?"
```

Inspect chunking without rebuilding Chroma:

```bash
python ingest.py
```

Test the OpenRouter debug path:

```bash
python debug_openrouter.py
```

## Notes

- `chroma_db/` is generated data and can be safely deleted and rebuilt.
- The sample workflow uses Ollama locally by default, so no external API key is required for the main path.
- `retriver.py` is the canonical rebuild script name in this repository, even though the spelling is historical.
- `debug_openrouter.py` and `agent.py` are exploratory scripts; they are not part of the main RAG flow.

> [!IMPORTANT]
> The first ingest run can take longer than later runs because embedding weights may need to download and the vector store is rebuilt from scratch.
