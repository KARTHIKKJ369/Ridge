import os
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

os.environ["USER_AGENT"] = "AgenticRAG/1.0"

# 1. Load a real document
print("Loading document...")
url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
loader = WebBaseLoader(url)
docs = loader.load()

# --- THE TUNING ZONE ---
# Try changing these numbers and running the script!
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

print(f"\nChopping with Size: {CHUNK_SIZE}, Overlap: {CHUNK_OVERLAP}...")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    # This tells it to try splitting by paragraphs first, then sentences, then words
    separators=["\n\n", "\n", ".", " ", ""] 
)

splits = text_splitter.split_documents(docs)

print(f"Total chunks created: {len(splits)}\n")

# Let's inspect a random sequence of chunks to see the overlap in action
start_index = 10
for i in range(start_index, start_index + 3):
    print(f"--- Chunk {i} ({len(splits[i].page_content)} chars) ---")
    print(splits[i].page_content)
    print("-" * 50 + "\n")