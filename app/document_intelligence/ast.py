"""
Unified Document AST (Abstract Syntax Tree)
===========================================
Defines the normalized, structure-aware internal representation for all ingested documents
regardless of source format (PDF, DOCX, PPTX, XLSX, CSV, Markdown, Web, Image).
Preserves layout hierarchies, section paths, bounding boxes, tables, and figures.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ElementType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CODE = "code"
    FORMULA = "formula"
    METADATA = "metadata"


class BlockAST(BaseModel):
    """Atomic structural unit within a document page."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    element_type: ElementType = ElementType.PARAGRAPH
    content: str = ""
    raw_content: str = ""
    page_number: int = 1
    section_path: str = ""
    heading: str = ""
    order: int = 0
    bbox: Optional[dict[str, float]] = None  # {x0, y0, x1, y1} normalized [0..1]
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_search_text(self) -> str:
        """Returns the optimal search representation including heading context."""
        prefix = f"[Context: {self.section_path}]\n" if self.section_path else ""
        return f"{prefix}{self.content}".strip()


class TableBlock(BlockAST):
    """Structured representation of tabular data."""
    element_type: ElementType = ElementType.TABLE
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    caption: str = ""
    markdown: str = ""
    structured_json: list[dict[str, Any]] = Field(default_factory=list)

    def generate_markdown(self) -> str:
        if self.markdown:
            return self.markdown
        if not self.headers and not self.rows:
            return self.content or ""
        
        lines = []
        if self.caption:
            lines.append(f"### Table: {self.caption}")
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        for row in self.rows:
            clean_row = [str(cell).replace("\n", " ").strip() for cell in row]
            # Pad row if shorter than headers
            if len(clean_row) < len(self.headers):
                clean_row.extend([""] * (len(self.headers) - len(clean_row)))
            lines.append("| " + " | ".join(clean_row) + " |")
        
        self.markdown = "\n".join(lines)
        return self.markdown

    def get_search_text(self) -> str:
        """Returns search-optimized text with captions, headers, and section context."""
        cap = f"Table: {self.caption}\n" if self.caption else ""
        sec = f"Section: {self.section_path}\n" if self.section_path else ""
        md = self.generate_markdown()
        return f"{sec}{cap}{md}".strip()


class FigureBlock(BlockAST):
    """Structured representation of visual figures, charts, and diagrams."""
    element_type: ElementType = ElementType.FIGURE
    caption: str = ""
    image_path: str = ""
    ocr_text: str = ""
    description: str = ""
    nearby_text: str = ""

    def get_search_text(self) -> str:
        parts = []
        if self.section_path:
            parts.append(f"[Section: {self.section_path}]")
        if self.caption:
            parts.append(f"Figure: {self.caption}")
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.ocr_text:
            parts.append(f"Text in figure: {self.ocr_text}")
        return "\n".join(parts) if parts else self.content


class PageAST(BaseModel):
    """A document page containing an ordered sequence of structural blocks."""
    page_number: int = 1
    blocks: list[BlockAST] = Field(default_factory=list)
    has_ocr: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_block(self, block: BlockAST):
        block.page_number = self.page_number
        block.order = len(self.blocks)
        self.blocks.append(block)

    @property
    def tables(self) -> list[TableBlock]:
        return [b for b in self.blocks if isinstance(b, TableBlock)]

    @property
    def figures(self) -> list[FigureBlock]:
        return [b for b in self.blocks if isinstance(b, FigureBlock)]


class DocumentAST(BaseModel):
    """The root Abstract Syntax Tree of an ingested document."""
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = Field(default="user_input")
    source_type: str = "file"  # file, url, text, image, scan
    source_url: str = ""
    mime_type: str = "application/octet-stream"
    pages: list[PageAST] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


    def all_blocks(self) -> list[BlockAST]:
        """Returns all structural blocks across all pages in reading order."""
        result = []
        for page in self.pages:
            result.extend(page.blocks)
        return result

    def all_tables(self) -> list[TableBlock]:
        """Returns all structured tables extracted from the document."""
        return [b for b in self.all_blocks() if isinstance(b, TableBlock)]

    def all_figures(self) -> list[FigureBlock]:
        """Returns all figures/diagrams extracted from the document."""
        return [b for b in self.all_blocks() if isinstance(b, FigureBlock)]

    def ocr_page_count(self) -> int:
        """Counts the number of pages that required OCR extraction."""
        return sum(1 for p in self.pages if p.has_ocr)

    def to_markdown(self) -> str:
        """Serializes the document AST into clean, formatted Markdown."""
        page_mds = []
        for page in self.pages:
            block_mds = []
            for b in page.blocks:
                if isinstance(b, TableBlock):
                    block_mds.append(b.generate_markdown())
                elif isinstance(b, FigureBlock):
                    cap = f"*{b.caption}*" if b.caption else ""
                    desc = f" ({b.description})" if b.description else ""
                    block_mds.append(f"![Figure: {cap}{desc}]({b.image_path})")
                elif b.element_type == ElementType.HEADING:
                    level = b.metadata.get("level", 2)
                    prefix = "#" * level
                    block_mds.append(f"{prefix} {b.content}")
                elif b.element_type == ElementType.CODE:
                    lang = b.metadata.get("language", "")
                    block_mds.append(f"```{lang}\n{b.content}\n```")
                else:
                    block_mds.append(b.content)
            if block_mds:
                page_mds.append(f"<!-- Page {page.page_number} -->\n" + "\n\n".join(block_mds))
        return "\n\n---\n\n".join(page_mds)
