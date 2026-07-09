import os
import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

os.environ["USER_AGENT"] = "AgenticRAG/1.0"

URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"


def clean_heading(text: str) -> str:
    return text.strip().removesuffix("#").strip()


def heading_lines(metadata: dict) -> list[str]:
    return [
        metadata[key]
        for key in ("h1", "h2", "h3")
        if metadata.get(key)
    ]


def format_section(section: Document) -> Document:
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
    print("Loading and splitting document by real headers...")
    sections = load_header_sections(URL)

    CHUNK_SIZE = 1500
    CHUNK_OVERLAP = 200

    print(f"\nChopping with Size: {CHUNK_SIZE}, Overlap: {CHUNK_OVERLAP}...")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )

    splits = [ensure_chunk_has_headings(chunk) for chunk in text_splitter.split_documents(sections)]

    print(f"Header sections created: {len(sections)}")
    print(f"Total final chunks created: {len(splits)}\n")

    # Let's inspect a random sequence of chunks to see the overlap in action
    start_index = min(10, max(0, len(splits) - 3))
    for i in range(start_index, min(start_index + 3, len(splits))):
        print(f"--- Chunk {i} ({len(splits[i].page_content)} chars) ---")
        print(f"Metadata: {splits[i].metadata}")
        print(splits[i].page_content)
        print("-" * 50 + "\n")


if __name__ == "__main__":
    main()
