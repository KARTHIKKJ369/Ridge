"""
Ridge: Universal Ingestion & Knowledge Crag Engine
===================================================
Supports multi-format parsing, hierarchical chunking, and persistent embedding into ChromaDB.

Supported Sources:
- Documents: PDF (.pdf), Microsoft Word (.docx), PowerPoint (.pptx), Markdown (.md), Plain Text (.txt)
- Tabular Data: Excel (.xlsx), CSV (.csv), TSV (.tsv)
- Code & Config: Python (.py), JavaScript/TypeScript (.js, .jsx, .ts, .tsx), Web (.html, .css),
                 Config (.json, .yaml, .yml, .toml, .ini), Database (.sql), Systems (.c, .cpp, .java, .go, .rs, .sh)
- Media & Subtitles: SubRip (.srt), WebVTT (.vtt)
- Web & Media URLs: YouTube Transcripts, GitHub Repos/Files, ArXiv Papers, and standard Web URLs.
"""

import os
import re
import csv
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Optional

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

DEFAULT_ARTICLE_URL = "https://lilianweng.github.io/posts/2023-06-23-agent/"
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_USER_AGENT = "RidgeCRAG/1.0"


# ---------------------------------------------------------------------------
# Shared Chunking and Heading Preservation Helpers
# ---------------------------------------------------------------------------

def clean_heading(text: str) -> str:
    return text.strip().removesuffix("#").strip()


def heading_lines(metadata: dict) -> list[str]:
    return [metadata[key] for key in ("h1", "h2", "h3") if metadata.get(key)]


def breadcrumb_string(metadata: dict) -> str:
    parts = []
    source = metadata.get("source")
    if source:
        src_name = source.split("/")[-1] if not is_url(source) else source
        parts.append(src_name)
    for key in ("h1", "h2", "h3"):
        val = metadata.get(key)
        if val:
            clean = clean_heading(str(val))
            if clean and clean not in parts:
                parts.append(clean)
    return " > ".join(parts) if parts else ""


def format_section(section: Document, source: str) -> Document:
    metadata = {"source": source, **section.metadata}
    breadcrumb = breadcrumb_string(metadata)
    if breadcrumb:
        metadata["breadcrumb"] = breadcrumb
    page_content = "\n".join(heading_lines(section.metadata) + [section.page_content]).strip()
    return Document(page_content=page_content, metadata=metadata)


def ensure_chunk_has_headings(chunk: Document) -> Document:
    meta = dict(chunk.metadata)
    breadcrumb = breadcrumb_string(meta)
    if breadcrumb:
        meta["breadcrumb"] = breadcrumb
    
    headings = heading_lines(meta)
    prefix_header = f"[Context: {breadcrumb}]" if breadcrumb else ""
    
    content = chunk.page_content
    if prefix_header and not content.startswith("[Context:"):
        content = f"{prefix_header}\n{content}"
    elif headings and not any(content.startswith(h) for h in headings):
        content = "\n".join(headings + [content]).strip()

    return Document(page_content=content, metadata=meta)


def _sub_chunk(sections: list[Document], size: int, overlap: int) -> list[Document]:
    """Runs long sections through a character-based splitter, preserving hierarchy."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "```", ".", " ", ""],
    )
    return [ensure_chunk_has_headings(chunk) for chunk in text_splitter.split_documents(sections)]


def is_url(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https")


# ---------------------------------------------------------------------------
# RapidOCR Engine (Lazy Initialized)
# ---------------------------------------------------------------------------

_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def extract_text_from_image(image_input) -> str:
    """Extracts text lines from an image path, PIL Image, or numpy array via RapidOCR."""
    import numpy as np
    from PIL import Image

    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
        img_np = np.array(img)
    elif isinstance(image_input, Image.Image):
        img_np = np.array(image_input.convert("RGB"))
    else:
        img_np = image_input

    engine = get_ocr_engine()
    result, _ = engine(img_np)
    if not result:
        return ""

    lines = [item[1] for item in result if item and len(item) > 1]
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# 1. PDF Loader (with Automatic Scanned PDF OCR Fallback)
# ---------------------------------------------------------------------------

def load_pdf(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    from langchain_community.document_loaders import PyPDFLoader
    import pypdf
    import io
    from PIL import Image

    docs = PyPDFLoader(path).load()
    total_text = "".join([d.page_content for d in docs]).strip()

    # If PDF has native selectable text, use fast digital extraction
    if len(total_text) >= 50:
        for d in docs:
            d.metadata["source"] = path
        return _sub_chunk(docs, chunk_size, chunk_overlap)

    # Scanned PDF detected -> Fallback to RapidOCR on page images
    print(f"  [OCR Fallback] Scanned PDF detected for '{Path(path).name}'. Running OCR on pages...")
    reader = pypdf.PdfReader(path)
    ocr_docs = []

    for i, page in enumerate(reader.pages, start=1):
        page_text_lines = []
        for img_obj in page.images:
            try:
                pil_img = Image.open(io.BytesIO(img_obj.data))
                extracted = extract_text_from_image(pil_img)
                if extracted:
                    page_text_lines.append(extracted)
            except Exception as e:
                print(f"    OCR failed on page {i} image: {e}")

        if page_text_lines:
            page_content = f"## Page {i} (Scanned Document)\n" + "\n".join(page_text_lines)
            ocr_docs.append(Document(page_content=page_content, metadata={"source": path, "h1": Path(path).stem, "h2": f"Page {i}"}))

    if not ocr_docs:
        # Fallback to whatever tiny text was found or empty placeholder
        ocr_docs = [Document(page_content=total_text or "[Empty Scanned PDF]", metadata={"source": path})]

    return _sub_chunk(ocr_docs, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 2. Image Loader (.png, .jpg, .jpeg, .webp, .bmp, .tiff)
# ---------------------------------------------------------------------------

def load_image(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    filename = Path(path).name
    extracted = extract_text_from_image(path)
    content = f"# Image Document: {filename}\n\n{extracted or '[No text detected in image]'}"
    doc = Document(page_content=content, metadata={"source": path, "h1": filename, "type": "image_ocr"})
    return _sub_chunk([doc], chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 2. Microsoft Word Loader (.docx)
# ---------------------------------------------------------------------------

def load_docx(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    import docx

    doc = docx.Document(path)
    sections = []
    current_h1 = Path(path).stem
    current_h2 = ""
    current_lines = []

    def flush():
        if current_lines:
            meta = {"source": path, "h1": current_h1}
            if current_h2:
                meta["h2"] = current_h2
            sections.append(Document(page_content="\n".join(current_lines).strip(), metadata=meta))

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name.lower() if p.style else ""
        if "heading 1" in style:
            flush()
            current_h1 = text
            current_h2 = ""
            current_lines = [f"# {text}"]
        elif "heading 2" in style:
            flush()
            current_h2 = text
            current_lines = [f"## {text}"]
        elif "heading 3" in style:
            current_lines.append(f"### {text}")
        else:
            current_lines.append(text)

    # Extract tables in document as markdown tables
    for table in doc.tables:
        rows_text = []
        for i, row in enumerate(table.rows):
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            rows_text.append("| " + " | ".join(cells) + " |")
            if i == 0:
                rows_text.append("| " + " | ".join(["---"] * len(cells)) + " |")
        if rows_text:
            current_lines.append("\n" + "\n".join(rows_text) + "\n")

    flush()
    if not sections:
        sections = [Document(page_content="[Empty Word Document]", metadata={"source": path})]
    return _sub_chunk(sections, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 3. Microsoft PowerPoint Loader (.pptx)
# ---------------------------------------------------------------------------

def load_pptx(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    import pptx

    prs = pptx.Presentation(path)
    sections = []

    for i, slide in enumerate(prs.slides, start=1):
        slide_title = f"Slide {i}"
        slide_text = []

        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    t = paragraph.text.strip()
                    if t:
                        if not slide_text and hasattr(shape, "is_placeholder") and shape.is_placeholder:
                            slide_title = f"Slide {i}: {t}"
                        slide_text.append(t)

        content = f"## {slide_title}\n" + "\n".join(slide_text)
        sections.append(Document(page_content=content, metadata={"source": path, "h1": Path(path).stem, "h2": slide_title}))

    if not sections:
        sections = [Document(page_content="[Empty Presentation]", metadata={"source": path})]
    return _sub_chunk(sections, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 4. Tabular Data: Excel (.xlsx) & CSV/TSV
# ---------------------------------------------------------------------------

def load_excel(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    sections = []

    for sheetname in wb.sheetnames:
        sheet = wb[sheetname]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        headers = [str(c or "").strip() for c in rows[0]]
        table_lines = [f"## Sheet: {sheetname}", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]

        for row in rows[1:1000]:  # Limit to 1000 rows per sheet
            if any(row):
                cells = [str(c or "").strip().replace("\n", " ") for c in row]
                table_lines.append("| " + " | ".join(cells) + " |")

        sections.append(Document(page_content="\n".join(table_lines), metadata={"source": path, "h1": Path(path).stem, "h2": f"Sheet: {sheetname}"}))

    if not sections:
        sections = [Document(page_content="[Empty Spreadsheet]", metadata={"source": path})]
    return _sub_chunk(sections, chunk_size, chunk_overlap)


def load_csv(path: str, chunk_size: int, chunk_overlap: int, delimiter: str = ",") -> list[Document]:
    sections = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if rows:
        headers = rows[0]
        table_lines = [f"## File: {Path(path).name}", "| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        for r in rows[1:1500]:
            if r:
                table_lines.append("| " + " | ".join([c.strip().replace("\n", " ") for c in r]) + " |")
        sections.append(Document(page_content="\n".join(table_lines), metadata={"source": path, "h1": Path(path).name}))
    else:
        sections.append(Document(page_content="[Empty CSV File]", metadata={"source": path}))

    return _sub_chunk(sections, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 5. Markdown & Code / Config Loaders
# ---------------------------------------------------------------------------

def load_markdown(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    sections = md_splitter.split_text(text)

    for s in sections:
        s.metadata["source"] = path

    formatted = [format_section(s, source=path) for s in sections]
    return _sub_chunk(formatted, chunk_size, chunk_overlap)


def load_code_or_text(path: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    ext = Path(path).suffix.lower()
    filename = Path(path).name

    # Wrap code files with markdown code blocks for syntactic context
    if ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".cpp", ".c", ".h", ".java", ".go", ".rs", ".sql", ".sh", ".json", ".yaml", ".yml", ".toml"):
        lang = ext.lstrip(".")
        if lang in ("yml", "yaml"): lang = "yaml"
        if lang in ("ts", "tsx"): lang = "typescript"
        if lang in ("js", "jsx"): lang = "javascript"
        if lang in ("py",): lang = "python"
        
        formatted_content = f"## Code File: {filename}\n```{lang}\n{text}\n```"
    else:
        formatted_content = f"## Document: {filename}\n{text}"

    doc = Document(page_content=formatted_content, metadata={"source": path, "h1": filename})
    return _sub_chunk([doc], chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 6. YouTube Transcripts Loader
# ---------------------------------------------------------------------------

def is_youtube_url(url: str) -> bool:
    parsed = urlparse(url)
    return "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc


def extract_youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/")
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0]
    return None


def load_youtube_transcript(url: str, chunk_size: int, chunk_overlap: int) -> list[Document]:
    video_id = extract_youtube_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract YouTube video ID from URL: {url}")

    # 1. Fetch Video Title via YouTube oEmbed API
    title = f"YouTube Video ({video_id})"
    try:
        oembed_res = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=5)
        if oembed_res.status_code == 200:
            title = oembed_res.json().get("title", title)
    except Exception:
        pass

    # 2. Fetch Transcript
    from youtube_transcript_api import YouTubeTranscriptApi

    try:
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
    except Exception as e:
        # Try fetching list of available languages
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript(['en', 'en-US', 'auto'])
            transcript_data = transcript.fetch()
        except Exception as e2:
            raise ValueError(f"Could not retrieve transcripts for YouTube video '{title}': {e2}")

    # Format transcript with timestamps
    sections = []
    current_lines = [f"# YouTube Video: {title}", f"Source URL: {url}\n"]
    current_time_str = "00:00"

    for entry in transcript_data:
        start_seconds = int(entry.get("start", 0))
        mins, secs = divmod(start_seconds, 60)
        hours, mins = divmod(mins, 60)
        time_tag = f"[{hours:02d}:{mins:02d}:{secs:02d}]" if hours > 0 else f"[{mins:02d}:{secs:02d}]"
        
        text = entry.get("text", "").replace("\n", " ").strip()
        if text:
            current_lines.append(f"{time_tag} {text}")

    full_transcript_text = "\n".join(current_lines)
    doc = Document(page_content=full_transcript_text, metadata={"source": url, "h1": title, "type": "youtube"})
    return _sub_chunk([doc], chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# 7. GitHub Raw & Web URLs Loader
# ---------------------------------------------------------------------------

def load_github_url(url: str, chunk_size: int, chunk_overlap: int, user_agent: str) -> list[Document]:
    # Convert github.com/owner/repo/blob/branch/file to raw.githubusercontent.com
    raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    res = requests.get(raw_url, timeout=15, headers={"User-Agent": user_agent})
    res.raise_for_status()

    filename = Path(urlparse(url).path).name or "GitHub Document"
    text = res.text
    if url.endswith(".md") or url.endswith(".markdown"):
        headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        sections = md_splitter.split_text(text)
        for s in sections:
            s.metadata["source"] = url
        return _sub_chunk([format_section(s, source=url) for s in sections], chunk_size, chunk_overlap)

    doc = Document(page_content=f"## File: {filename}\n```\n{text}\n```", metadata={"source": url, "h1": filename})
    return _sub_chunk([doc], chunk_size, chunk_overlap)


def load_header_sections(url: str, user_agent: str = DEFAULT_USER_AGENT) -> list[Document]:
    response = requests.get(url, timeout=30, headers={"User-Agent": user_agent})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for noisy in soup.select("nav, .toc, .table-of-contents, #table-of-contents, script, style, footer"):
        noisy.decompose()

    page_title = (soup.title.string if soup.title else "").strip() or urlparse(url).netloc
    article = soup.select_one("article") or soup.select_one(".post-content") or soup.select_one("main") or soup.body

    sections = []
    current_metadata = {"h1": page_title}
    current_lines = [f"# {page_title}"]

    def flush_section():
        if current_lines:
            sections.append(
                format_section(
                    Document(
                        page_content="\n".join(current_lines).strip(),
                        metadata=current_metadata.copy(),
                    ),
                    source=url,
                )
            )

    for element in article.find_all(["h1", "h2", "h3", "p", "li", "pre", "table"]):
        if element.name in {"h1", "h2", "h3"}:
            flush_section()
            current_lines = []

            level = int(element.name[1])
            heading = clean_heading(element.get_text(" ", strip=True))
            if level == 1:
                current_metadata = {"h1": heading}
            elif level == 2:
                current_metadata = {"h1": current_metadata.get("h1", page_title), "h2": heading}
            else:
                current_metadata = {
                    "h1": current_metadata.get("h1", page_title),
                    "h2": current_metadata.get("h2", ""),
                    "h3": heading,
                }
            continue

        text = element.get_text(" ", strip=True)
        if text:
            current_lines.append(text)

    flush_section()
    return sections


def load_url(url: str, chunk_size: int, chunk_overlap: int, user_agent: str) -> list[Document]:
    if is_youtube_url(url):
        return load_youtube_transcript(url, chunk_size, chunk_overlap)

    if "github.com" in url and ("/blob/" in url or "/raw/" in url):
        return load_github_url(url, chunk_size, chunk_overlap, user_agent)

    sections = load_header_sections(url, user_agent=user_agent)
    return _sub_chunk(sections, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# Universal Dispatcher
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

    # 1. URL Dispatching
    if is_url(source):
        return load_url(source, size, overlap, agent)

    # 2. File Extension Dispatching
    suffix = Path(source).suffix.lower()

    if suffix == ".pdf":
        return load_pdf(source, size, overlap)
    
    if suffix in (".docx", ".doc"):
        return load_docx(source, size, overlap)

    if suffix in (".pptx", ".ppt"):
        return load_pptx(source, size, overlap)

    if suffix in (".xlsx", ".xls"):
        return load_excel(source, size, overlap)

    if suffix == ".csv":
        return load_csv(source, size, overlap, delimiter=",")

    if suffix == ".tsv":
        return load_csv(source, size, overlap, delimiter="\t")

    if suffix in (".md", ".markdown"):
        return load_markdown(source, size, overlap)

    # Images (PNG, JPG, JPEG, WEBP, BMP, TIFF) via RapidOCR
    if suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"):
        return load_image(source, size, overlap)

    # Code, Config, Subtitles, Plain Text
    if suffix in (
        ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".sql", ".html", ".htm", ".css", ".cpp", ".c", ".h",
        ".java", ".go", ".rs", ".sh", ".bash", ".zsh", ".srt", ".vtt", ""
    ):
        return load_code_or_text(source, size, overlap)

    raise ValueError(
        f"Unsupported file format '{suffix}'. Supported: .pdf, .png, .jpg, .docx, .pptx, .xlsx, .csv, .md, .txt, .py, .js, .ts, .json, .yaml, YouTube URLs, and Web URLs."
    )


def load_and_split_sources(sources: list[str], **kwargs) -> list[Document]:
    all_splits = []
    for source in sources:
        print(f"  Loading: {source}")
        splits = load_and_split_source(source, **kwargs)
        print(f"    -> {len(splits)} chunks")
        all_splits.extend(splits)
    return all_splits


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