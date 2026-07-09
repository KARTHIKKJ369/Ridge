import os

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


DEFAULT_ARTICLE_URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_USER_AGENT = "AgenticRAG/1.0"


def clean_heading(text: str) -> str:
    return text.strip().removesuffix("#").strip()


def heading_lines(metadata: dict) -> list[str]:
    return [
        metadata[key]
        for key in ("h1", "h2", "h3")
        if metadata.get(key)
    ]


def format_section(section: Document, source_url: str) -> Document:
    page_content = "\n".join(heading_lines(section.metadata) + [section.page_content]).strip()
    metadata = {"source": source_url, **section.metadata}
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
                    source_url=url,
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


def split_article(
    url: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    user_agent: str | None = None,
) -> list[Document]:
    article_url = url or os.getenv("ARTICLE_URL", DEFAULT_ARTICLE_URL)
    size = chunk_size or int(os.getenv("CHUNK_SIZE", DEFAULT_CHUNK_SIZE))
    overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP))
    agent = user_agent or os.getenv("USER_AGENT", DEFAULT_USER_AGENT)

    sections = load_header_sections(article_url, user_agent=agent)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    return [ensure_chunk_has_headings(chunk) for chunk in text_splitter.split_documents(sections)]
