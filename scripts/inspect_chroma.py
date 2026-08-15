"""
Run this on the machine where ./chroma_db lives (same folder as main.py).
Dumps every chunk in the vector store and flags any that mention known
Task Decomposition methods, so we can see if the real content exists at all
independent of retrieval/MMR ranking.
"""
import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

all_data = vectorstore.get()
docs = all_data["documents"]

print(f"Total chunks in DB: {len(docs)}\n")

keywords = ["Chain of Thought", "Tree of Thoughts", "LLM+P", "CoT prompting", "decomposition"]

for i, doc in enumerate(docs):
    hits = [kw for kw in keywords if kw.lower() in doc.lower()]
    marker = f"  <-- MATCHES: {hits}" if hits else ""
    print(f"--- Chunk {i} ({len(doc)} chars){marker} ---")
    print(doc[:300].replace("\n", " "))
    print()