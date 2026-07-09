# Recall

A small RAG experiment over Lilian Weng's "LLM Powered Autonomous Agents" post.

The project builds a local Chroma vector database from the article, retrieves relevant chunks, grades them with a LangGraph workflow, and asks an Ollama-hosted chat model to answer using only the retrieved context.

## What is in here

- `retriver.py` - main ingestion script. Fetches the article, splits it by real HTML headings, sub-chunks large sections, rebuilds `chroma_db`, and prints a retrieval sanity check.
- `main.py` - LangGraph RAG workflow: retrieve, grade, optionally rewrite, then generate.
- `ingest.py` - chunking inspection helper for debugging ingestion without writing Chroma.
- `debug_openrouter.py` and `agent.py` - older OpenRouter/debug experiments.

## Setup

Create and activate a virtual environment:

```bash
python -m venv recall-env
source recall-env/bin/activate
pip install -r requirements.txt
```

Optional: create a `.env` file from the example if you want to use the OpenRouter debug scripts:

```bash
cp .env.example .env
```

`main.py` currently uses Ollama at:

```text
http://100.75.99.22:11434
```

with model:

```text
gemma4:12b
```

Change those values in `main.py` if your Ollama server or model name is different.

## Usage

Rebuild the local vector database:

```bash
source recall-env/bin/activate
python retriver.py
```

Run the RAG workflow:

```bash
python main.py
```

Inspect chunking without rebuilding Chroma:

```bash
python ingest.py
```

## Notes

- `chroma_db/` is generated data and can be rebuilt with `python retriver.py`.
- The ingestion step needs network access to fetch the blog post and may contact Hugging Face when loading the embedding model.
- The first embedding load can take a little while because model weights may need to be downloaded.
