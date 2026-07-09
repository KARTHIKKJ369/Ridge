import os
import shutil

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

os.environ["USER_AGENT"] = "AgenticRAG/1.0"

URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"
PERSIST_DIR = "./chroma_db"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


def clean_heading(text: str) -> str:
    return text.strip().removesuffix("#").strip()


def heading_lines(metadata: dict) -> list[str]:
    return [
        metadata[key]
        for key in ("h1", "h2", "h3")
        if metadata.get(key)
    ]


def format_section(section: Document) -> Document:
    """Put header metadata back into the searchable text."""
    page_content = "\n".join(heading_lines(section.metadata) + [section.page_content]).strip()
    metadata = {"source": URL, **section.metadata}
    return Document(page_content=page_content, metadata=metadata)


def ensure_chunk_has_headings(chunk: Document) -> Document:
    headings = heading_lines(chunk.metadata)
    if not headings:
        return chunk

    first_heading = headings[0]
    if chunk.page_content.startswith(first_heading):
        return chunk

    return Document(
        page_content="\n".join(headings + [chunk.page_content]).strip(),
        metadata=chunk.metadata,
    )


def load_header_sections(url: str) -> list[Document]:
    response = requests.get(url, timeout=30, headers={"User-Agent": os.environ["USER_AGENT"]})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for noisy in soup.select("nav, .toc, .table-of-contents, #table-of-contents"):
        noisy.decompose()

    article = soup.select_one("article") or soup.select_one(".post-content") or soup.body

    sections = []
    current_metadata = {}
    current_lines = []

    def flush_section():
        if current_lines and current_metadata:
            sections.append(
                format_section(
                    Document(
                        page_content="\n".join(current_lines).strip(),
                        metadata=current_metadata.copy(),
                    )
                )
            )

    for element in article.find_all(["h1", "h2", "h3", "p", "li", "pre"]):
        if element.name in {"h1", "h2", "h3"}:
            flush_section()
            current_lines = []

            level = int(element.name[1])
            heading = clean_heading(element.get_text(" ", strip=True))
            if level == 1:
                current_metadata = {"h1": heading}
            elif level == 2:
                current_metadata = {
                    "h1": current_metadata.get("h1"),
                    "h2": heading,
                }
            else:
                current_metadata = {
                    "h1": current_metadata.get("h1"),
                    "h2": current_metadata.get("h2"),
                    "h3": heading,
                }
            continue

        text = element.get_text(" ", strip=True)
        if text and current_metadata:
            current_lines.append(text)

    flush_section()
    return sections


def main():
    print("1. Downloading a free Embedding Model (this takes a few seconds the first time)...")
    # This runs locally on your machine, so it's 100% free.
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("2. Loading and splitting the web article by real headers...")
    sections = load_header_sections(URL)

    print("3. Sub-chunking only if a header section is too large...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    splits = [ensure_chunk_has_headings(chunk) for chunk in text_splitter.split_documents(sections)]

    print(f"   Created {len(sections)} header sections and {len(splits)} final chunks.")

    print("4. Rebuilding the Chroma Vector Database...")
    # This converts the text chunks into math (vectors) and saves them in a folder called 'chroma_db'
    if os.path.exists(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=PERSIST_DIR # Saves to your hard drive so you don't have to rebuild it
    )

    print("\n=== LET'S TEST THE RETRIEVER ===")
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    question = "What is task decomposition in LLM agents?"
    print(f"Question: '{question}'")

    retrieved_docs = retriever.invoke(question)

    for i, doc in enumerate(retrieved_docs):
        print(f"\n--- Result {i+1} ---")
        print(doc.page_content)


if __name__ == "__main__":
    main()
