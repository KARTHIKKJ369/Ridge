"""
Hierarchical Document & Section Summarizer
==========================================
Generates high-level document and section summaries during ingestion,
indexing them as specialized summary chunks for global thematic queries.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from app.document_intelligence.ast import DocumentAST, ElementType
from app.document_intelligence.chunker import StructuredChunk

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are an AI document intelligence system.
Analyze the following document text and produce a concise 3-5 sentence executive summary covering:
1. Core subject matter and main purpose
2. Key topics, entities, and findings
3. Major sections covered

Document Text:
{text}

Executive Summary:"""


class HierarchicalSummarizer:
    """
    Generates document-level and section-level summaries from DocumentAST.
    Outputs StructuredChunk objects tagged with content_type="summary".
    """
    def __init__(self, enabled: Optional[bool] = None):
        env_val = os.getenv("ENABLE_HIERARCHICAL_SUMMARIES", "true").lower()
        self.enabled = (env_val in ("true", "1", "yes")) if enabled is None else enabled
        self._llm = None

    def _get_fast_llm(self):
        if self._llm is None:
            try:
                from main import get_settings
                from langchain_groq import ChatGroq

                settings = get_settings()
                if settings.get("groq_api_key"):
                    self._llm = ChatGroq(
                        api_key=settings["groq_api_key"],
                        model_name=settings.get("groq_fast_model", "openai/gpt-oss-20b"),
                        temperature=0.3,
                        max_tokens=256,
                    )
            except Exception as e:
                logger.warning(f"Fast LLM initialization note for Summarizer: {e}")
        return self._llm

    def generate_document_summary(self, doc_ast: DocumentAST) -> Optional[StructuredChunk]:
        """Generates an executive summary chunk for the entire document."""
        if not self.enabled:
            return None

        # Build preview text from headings and initial paragraphs
        preview_blocks = []
        for b in doc_ast.all_blocks()[:20]:
            if b.element_type in (ElementType.HEADING, ElementType.PARAGRAPH):
                preview_blocks.append(f"{b.heading}: {b.content}" if b.heading else b.content)

        if not preview_blocks:
            return None

        combined_text = "\n".join(preview_blocks)[:3500]
        summary_text = ""

        llm = self._get_fast_llm()
        if llm:
            try:
                prompt = SUMMARY_PROMPT.format(text=combined_text)
                res = llm.invoke(prompt)
                summary_text = re.sub(r"<.*?>", "", res.content).strip()
            except Exception as err:
                logger.warning(f"LLM summary generation note: {err}")

        # Deterministic fallback summary if LLM not available
        if not summary_text:
            headings = [b.content for b in doc_ast.all_blocks() if b.element_type == ElementType.HEADING]
            top_headings = ", ".join(headings[:6]) if headings else "General Topics"
            summary_text = (
                f"Document overview for {doc_ast.filename}. "
                f"Contains {len(doc_ast.pages)} pages covering: {top_headings}."
            )

        search_rep = f"[Document Summary: {doc_ast.filename}]\n{summary_text}"
        return StructuredChunk(
            content=search_rep,
            raw_content=summary_text,
            contextual_content=f"[Document Summary: {doc_ast.filename}]",
            content_type="summary",
            heading="Document Executive Summary",
            section="Executive Summary",
            section_path=f"{doc_ast.filename} > Executive Summary",
            metadata={"is_summary": True, "summary_level": "document", "source": doc_ast.filename},
        )


# Global singleton
_summarizer: Optional[HierarchicalSummarizer] = None


def get_hierarchical_summarizer() -> HierarchicalSummarizer:
    global _summarizer
    if _summarizer is None:
        _summarizer = HierarchicalSummarizer()
    return _summarizer
