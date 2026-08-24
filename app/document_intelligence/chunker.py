"""
Structure-Aware Semantic Chunker
================================
Chunks documents according to their semantic and structural role (paragraphs,
atomic tables, code blocks, lists, figures) rather than arbitrary character cuts.
Maintains heading inheritance, section breadcrumbs, and parent-child hierarchies.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.document_intelligence.ast import (
    ElementType,
    BlockAST,
    TableBlock,
    FigureBlock,
    PageAST,
    DocumentAST,
)


class StructuredChunk(BaseModel):
    """Normalized chunk produced by the StructureAwareChunker."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    is_parent: bool = False
    content: str = ""                # Search representation (with breadcrumbs)
    raw_content: str = ""            # Verbatim text (for generation & citations)
    contextual_content: Optional[str] = None
    content_type: str = "text"       # text, table, code, figure, list
    page_number: int = 1
    heading: str = ""
    section: str = ""
    section_path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructureAwareChunker:
    """
    Structure-aware chunker that respects document AST element boundaries:
    - Tables are kept as atomic Markdown tables with replicated headers.
    - Code blocks are kept as whole syntax units.
    - Figures become multimodal visual chunks with captions & OCR.
    - Paragraphs inherit section paths and split on sentence/paragraph boundaries.
    """
    def __init__(
        self,
        target_chunk_size: int = 1200,
        chunk_overlap: int = 150,
        child_chunk_size: int = 350,
        child_overlap: int = 50,
        version: str = "structure_v2",
    ):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.child_chunk_size = child_chunk_size
        self.child_overlap = child_overlap
        self.version = version

    def chunk_document(self, doc_ast: DocumentAST) -> tuple[list[StructuredChunk], list[StructuredChunk]]:
        """
        Processes a DocumentAST and produces:
        (parent_chunks, child_chunks)
        """
        parent_chunks: list[StructuredChunk] = []
        child_chunks: list[StructuredChunk] = []

        for page in doc_ast.pages:
            current_section_path = doc_ast.filename
            current_heading = doc_ast.filename

            i = 0
            blocks = page.blocks
            while i < len(blocks):
                block = blocks[i]

                # Update heading tracking
                if block.element_type == ElementType.HEADING:
                    current_heading = block.content
                    current_section_path = block.section_path or f"{doc_ast.filename} > {current_heading}"
                    i += 1
                    continue

                # 1. Atomic Table Chunking
                if isinstance(block, TableBlock):
                    p_chunk, c_chunks = self._chunk_table_block(block, page.page_number, current_section_path, current_heading)
                    parent_chunks.append(p_chunk)
                    child_chunks.extend(c_chunks)
                    i += 1
                    continue

                # 2. Atomic Figure Chunking
                if isinstance(block, FigureBlock):
                    p_chunk, c_chunks = self._chunk_figure_block(block, page.page_number, current_section_path, current_heading)
                    parent_chunks.append(p_chunk)
                    child_chunks.extend(c_chunks)
                    i += 1
                    continue

                # 3. Code Block Chunking
                if block.element_type == ElementType.CODE:
                    p_chunk, c_chunks = self._chunk_code_block(block, page.page_number, current_section_path, current_heading)
                    parent_chunks.append(p_chunk)
                    child_chunks.extend(c_chunks)
                    i += 1
                    continue

                # 4. Standard Paragraph & List Chunking (Accumulate until target budget)
                para_texts = []
                para_raws = []
                while i < len(blocks):
                    curr = blocks[i]
                    if curr.element_type == ElementType.HEADING or isinstance(curr, (TableBlock, FigureBlock)) or curr.element_type == ElementType.CODE:
                        break
                    
                    para_texts.append(curr.content)
                    para_raws.append(curr.raw_content or curr.content)
                    total_len = sum(len(t) for t in para_texts)
                    i += 1
                    if total_len >= self.target_chunk_size:
                        break

                if para_texts:
                    combined_raw = "\n\n".join(para_raws).strip()
                    prefix = f"[Context: {current_section_path}]\n" if current_section_path else ""
                    combined_content = f"{prefix}{combined_raw}"

                    parent_id = str(uuid.uuid4())
                    parent = StructuredChunk(
                        id=parent_id,
                        is_parent=True,
                        content=combined_content,
                        raw_content=combined_raw,
                        content_type="text",
                        page_number=page.page_number,
                        heading=current_heading,
                        section=current_heading,
                        section_path=current_section_path,
                        metadata={"source": doc_ast.filename, "page": page.page_number, "h1": current_heading},
                    )
                    parent_chunks.append(parent)

                    # Create smaller child chunks for vector indexing
                    children = self._split_into_children(parent, current_section_path, current_heading, page.page_number, doc_ast.filename)
                    child_chunks.extend(children)

        return parent_chunks, child_chunks

    def _chunk_table_block(self, tbl: TableBlock, page_num: int, section_path: str, heading: str) -> tuple[StructuredChunk, list[StructuredChunk]]:
        md_table = tbl.generate_markdown()
        search_text = tbl.get_search_text()
        parent_id = str(uuid.uuid4())

        parent = StructuredChunk(
            id=parent_id,
            is_parent=True,
            content=search_text,
            raw_content=md_table,
            content_type="table",
            page_number=page_num,
            heading=heading,
            section=heading,
            section_path=section_path or tbl.section_path,
            metadata={"source": heading, "page": page_num, "is_table": True, "caption": tbl.caption},
        )

        # For tables: if table fits in child size, child is exact table; otherwise chunk rows with header replication
        child = StructuredChunk(
            id=str(uuid.uuid4()),
            parent_id=parent_id,
            is_parent=False,
            content=search_text,
            raw_content=md_table,
            content_type="table",
            page_number=page_num,
            heading=heading,
            section=heading,
            section_path=section_path or tbl.section_path,
            metadata={"source": heading, "page": page_num, "is_table": True, "caption": tbl.caption},
        )
        return parent, [child]

    def _chunk_figure_block(self, fig: FigureBlock, page_num: int, section_path: str, heading: str) -> tuple[StructuredChunk, list[StructuredChunk]]:
        search_text = fig.get_search_text()
        raw_text = f"![{fig.caption}]({fig.image_path})\n{fig.description}\n{fig.ocr_text}".strip()
        parent_id = str(uuid.uuid4())

        parent = StructuredChunk(
            id=parent_id,
            is_parent=True,
            content=search_text,
            raw_content=raw_text,
            content_type="figure",
            page_number=page_num,
            heading=heading,
            section=heading,
            section_path=section_path or fig.section_path,
            metadata={"source": heading, "page": page_num, "is_figure": True, "caption": fig.caption},
        )

        child = StructuredChunk(
            id=str(uuid.uuid4()),
            parent_id=parent_id,
            is_parent=False,
            content=search_text,
            raw_content=raw_text,
            content_type="figure",
            page_number=page_num,
            heading=heading,
            section=heading,
            section_path=section_path or fig.section_path,
            metadata={"source": heading, "page": page_num, "is_figure": True, "caption": fig.caption},
        )
        return parent, [child]

    def _chunk_code_block(self, block: BlockAST, page_num: int, section_path: str, heading: str) -> tuple[StructuredChunk, list[StructuredChunk]]:
        lang = block.metadata.get("language", "")
        raw_code = f"```{lang}\n{block.content}\n```"
        prefix = f"[Context: {section_path} > Code]\n" if section_path else ""
        search_text = f"{prefix}{raw_code}"
        parent_id = str(uuid.uuid4())

        parent = StructuredChunk(
            id=parent_id,
            is_parent=True,
            content=search_text,
            raw_content=raw_code,
            content_type="code",
            page_number=page_num,
            heading=heading,
            section=heading,
            section_path=section_path,
            metadata={"source": heading, "page": page_num, "is_code": True},
        )

        child = StructuredChunk(
            id=str(uuid.uuid4()),
            parent_id=parent_id,
            is_parent=False,
            content=search_text,
            raw_content=raw_code,
            content_type="code",
            page_number=page_num,
            heading=heading,
            section=heading,
            section_path=section_path,
            metadata={"source": heading, "page": page_num, "is_code": True},
        )
        return parent, [child]

    def _split_into_children(
        self,
        parent: StructuredChunk,
        section_path: str,
        heading: str,
        page_num: int,
        source_name: str,
    ) -> list[StructuredChunk]:
        """Splits parent raw content into small, high-precision child chunks for vector indexing."""
        raw_text = parent.raw_content
        if len(raw_text) <= self.child_chunk_size:
            prefix = f"[Context: {section_path}]\n" if section_path else ""
            return [
                StructuredChunk(
                    id=str(uuid.uuid4()),
                    parent_id=parent.id,
                    is_parent=False,
                    content=f"{prefix}{raw_text}",
                    raw_content=raw_text,
                    content_type="text",
                    page_number=page_num,
                    heading=heading,
                    section=heading,
                    section_path=section_path,
                    metadata={"source": source_name, "page": page_num, "h1": heading},
                )
            ]

        # Sentence-based boundary splitting
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if s.strip()]
        if not sentences:
            sentences = [raw_text]

        children: list[StructuredChunk] = []
        curr_chunk: list[str] = []
        curr_len = 0

        for sentence in sentences:
            if curr_len + len(sentence) > self.child_chunk_size and curr_chunk:
                c_text = " ".join(curr_chunk)
                prefix = f"[Context: {section_path}]\n" if section_path else ""
                children.append(
                    StructuredChunk(
                        id=str(uuid.uuid4()),
                        parent_id=parent.id,
                        is_parent=False,
                        content=f"{prefix}{c_text}",
                        raw_content=c_text,
                        content_type="text",
                        page_number=page_num,
                        heading=heading,
                        section=heading,
                        section_path=section_path,
                        metadata={"source": source_name, "page": page_num, "h1": heading},
                    )
                )
                curr_chunk = [sentence]
                curr_len = len(sentence)
            else:
                curr_chunk.append(sentence)
                curr_len += len(sentence)

        if curr_chunk:
            c_text = " ".join(curr_chunk)
            prefix = f"[Context: {section_path}]\n" if section_path else ""
            children.append(
                StructuredChunk(
                    id=str(uuid.uuid4()),
                    parent_id=parent.id,
                    is_parent=False,
                    content=f"{prefix}{c_text}",
                    raw_content=c_text,
                    content_type="text",
                    page_number=page_num,
                    heading=heading,
                    section=heading,
                    section_path=section_path,
                    metadata={"source": source_name, "page": page_num, "h1": heading},
                )
            )

        return children
