"""
Ridge: Ingestion and Knowledge Topo Parser
=========================================
Handles multi-format document loading, markdown/hierarchical section splitting,
and persistent vector embedding into ChromaDB.
Supported sources: PDF, Markdown, Plain Text, and Web URLs.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

DEFAULT_ARTICLE_URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_USER_AGENT = "AgenticRAG/1.0"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def clean_heading(text: str) -> str:
    return text.strip().removesuffix("#").strip()


def heading_lines(metadata: dict) -> list[str]:
    return [metadata[key] for key in ("h1", "h2", "h3") if metadata.get(key)]


def format_section(section: Document, source: str) -> Document:
    page_content = "\n".join(heading_lines(section.metadata) + [section.page_content]).strip()
    metadata = {"source": source, **section.metadata}
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


def _sub_chunk(sections: list[Document], size: int, overlap: int) -> list[Document]:
    """Runs long sections through a char-based splitter, re-attaching headings if split."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return [ensure_chunk_has_headings(chunk) for chunk in text_splitter.split_documents(sections)]


def is_url(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https")


# ---------------------------------------------------------------------------
# URL / HTML loader (header-aware, via BeautifulSoup)
# ---------------------------------------------------------------------------

def load_header_sections(url: str, user_agent: str = DEFAULT_USER_AGENT) -> list[Document]:
    response = requests.get(url, timeout=30, headers={"User-Agent": user_agent})
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
                    ),
                    source=url,
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
                current_metadata = {"h1": current_metadata.get("h1"), "h2": heading}
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


def load_url(url: str, chunk_size: int, chunk_overlap: int, user_agent: str) -> list[Document]:
    sections = load_header_sections(url, user_agent=user_agent)
    return _sub_chunk(sections, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# PDF loader
# ---------------------------------------------------------------------------

def load_pdf(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    from langchain_community.document_loaders import PyPDFLoader

    docs = PyPDFLoader(path).load()
    for d in docs:
        d.metadata["source"] = path
    return _sub_chunk(docs, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# Markdown loader (header-aware, via MarkdownHeaderTextSplitter)
# ---------------------------------------------------------------------------

def load_markdown(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8")

    headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    sections = md_splitter.split_text(text)

    for s in sections:
        s.metadata["source"] = path

    formatted = [format_section(s, source=path) for s in sections]
    return _sub_chunk(formatted, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# Plain text loader (no header structure to preserve)
# ---------------------------------------------------------------------------

def load_text(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8")
    doc = Document(page_content=text, metadata={"source": path})
    return _sub_chunk([doc], chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def load_and_split_source(
    source: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    user_agent: str | None = None,
) -> list[Document]:
    size = chunk_size or int(os.getenv("CHUNK_SIZE", DEFAULT_CHUNK_SIZE))
    overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP))
    agent = user_agent or os.getenv("USER_AGENT", DEFAULT_USER_AGENT)

    if is_url(source):
        return load_url(source, size, overlap, agent)

    suffix = Path(source).suffix.lower()
    if suffix == ".pdf":
        return load_pdf(source, size, overlap)
    if suffix in (".md", ".markdown"):
        return load_markdown(source, size, overlap)
    if suffix in (".txt", ""):
        return load_text(source, size, overlap)

    raise ValueError(
        f"Unsupported source type for '{source}'. Supported: http(s):// URLs, .pdf, .md, .txt"
    )


def load_and_split_sources(sources: list[str], **kwargs) -> list[Document]:
    all_splits = []
    for source in sources:
        print(f"  Loading: {source}")
        splits = load_and_split_source(source, **kwargs)
        print(f"    -> {len(splits)} chunks")
        all_splits.extend(splits)
    return all_splits


# Backward-compatible alias for the old single-article API
def split_article(
    url: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    user_agent: str | None = None,
) -> list[Document]:
    article_url = url or os.getenv("ARTICLE_URL", DEFAULT_ARTICLE_URL)
    return load_and_split_source(
        article_url,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        user_agent=user_agent,
    )