import os
import shutil

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from rag_ingest import DEFAULT_ARTICLE_URL, split_article


load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
ARTICLE_URL = os.getenv("ARTICLE_URL", DEFAULT_ARTICLE_URL)


def rebuild_vectorstore():
    print("1. Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    print("2. Loading and splitting the article by real headers...")
    splits = split_article(url=ARTICLE_URL)
    print(f"   Created {len(splits)} final chunks.")

    print("3. Rebuilding the Chroma vector database...")
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    return Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )


def main():
    vectorstore = rebuild_vectorstore()

    print("\n=== RETRIEVAL SANITY CHECK ===")
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    question = "What is task decomposition in LLM agents?"
    print(f"Question: '{question}'")

    retrieved_docs = retriever.invoke(question)
    for i, doc in enumerate(retrieved_docs):
        print(f"\n--- Result {i + 1} ---")
        print(doc.page_content)


if __name__ == "__main__":
    main()
