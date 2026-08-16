import os
import shutil
import sys

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from rag_ingest import DEFAULT_ARTICLE_URL, load_and_split_sources


load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def get_device() -> str:
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def rebuild_vectorstore(sources: list[str]) -> Chroma:
    device = get_device()
    print(f"1. Loading embedding model ({EMBEDDING_MODEL}) on {device.upper()}...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

    print(f"2. Loading and splitting {len(sources)} source(s)...")
    splits = load_and_split_sources(sources)
    print(f"   Created {len(splits)} total chunks.")

    print("3. Rebuilding the Chroma vector database...")
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    return Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )


def main() -> None:
    # Sources: any mix of http(s):// URLs, .pdf, .md, .txt file paths.
    # e.g. python retriver.py https://example.com/post1 ./notes.pdf ./readme.md
    sources = sys.argv[1:] or [os.getenv("ARTICLE_URL", DEFAULT_ARTICLE_URL)]

    vectorstore = rebuild_vectorstore(sources)

    print("\n=== RETRIEVAL SANITY CHECK ===")
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    question = "What is task decomposition in LLM agents?"
    print(f"Question: '{question}'")

    retrieved_docs = retriever.invoke(question)
    for i, doc in enumerate(retrieved_docs):
        print(f"\n--- Result {i + 1} (source: {doc.metadata.get('source', '?')}) ---")
        print(doc.page_content)


if __name__ == "__main__":
    main()