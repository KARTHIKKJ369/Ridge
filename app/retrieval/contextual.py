"""
Anthropic-Style Contextual Retrieval Engine
===========================================
Generates situated contextual representations for retrievable chunks,
positioning each chunk within the global context of its parent document.

Architecture:
- Single-Pass Document Overview: Generates document-level situated context in at most 1 fast LLM call
  (rather than N per-chunk LLM calls which cause HTTP 429 rate limit backoffs).
- Deterministic Hierarchy Mapping: Combines document scope with section breadcrumbs and page numbers.
- Zero-Delay Fallback: Immediate sub-millisecond fallback if LLM is rate-limited or offline.
- Zero Citation Pollution: Enriches search representation (contextual_content) while keeping raw_content clean.
"""
from __future__ import annotations

import os
import re
import logging
from typing import Optional

from app.document_intelligence.chunker import StructuredChunk

logger = logging.getLogger(__name__)

DOC_SITUATE_PROMPT = """<document>
{document_preview}
</document>

Provide a concise 1-2 sentence (maximum 40 words) description of this document's primary subject, domain, entity, and scope.
Answer with only the succinct description:"""


class ContextualRetrievalEngine:
    """
    Enriches chunks with situated contextual summaries prior to vector embedding and FTS indexing.
    Preserves raw_content for generation and citations.
    """
    def __init__(
        self,
        enabled: Optional[bool] = None,
        max_context_words: int = 60,
    ):
        env_val = os.getenv("ENABLE_CONTEXTUAL_RETRIEVAL", "true").lower()
        self.enabled = (env_val in ("true", "1", "yes")) if enabled is None else enabled
        self.max_context_words = max_context_words
        self._llm = None

    def _get_fast_llm(self):
        """Initializes fast LLM using Ridge's existing Groq / LangChain settings."""
        if self._llm is None:
            try:
                from app.graph.llm_factory import create_llm
                self._llm = create_llm(
                    temperature=0.2,
                    max_tokens=96,
                    is_fast_model=True,
                )
            except Exception as e:
                logger.warning(f"Fast LLM initialization note for Contextual Retrieval: {e}")
        return self._llm

    def generate_deterministic_context(self, chunk: StructuredChunk, doc_title: str = "") -> str:
        """
        Fast deterministic fallback: constructs situated context from document title,
        section breadcrumbs, page numbers, and structural element types.
        Takes 0 ms and never rate-limits.
        """
        parts = []
        clean_title = doc_title or chunk.metadata.get("source", "Document")
        parts.append(f"Document: {clean_title}")

        if chunk.section_path:
            parts.append(f"Section: {chunk.section_path}")
        elif chunk.heading:
            parts.append(f"Heading: {chunk.heading}")

        if chunk.page_number:
            parts.append(f"Page {chunk.page_number}")

        if chunk.content_type == "table":
            parts.append("Tabular Data")
        elif chunk.content_type == "figure":
            parts.append("Visual Figure")
        elif chunk.content_type == "code":
            parts.append("Code Syntax")

        return f"[{' | '.join(parts)}]"

    def extract_document_situated_scope(self, doc_text: str, doc_title: str = "") -> str:
        """
        Extracts a single global situated scope description for the whole document in 1 fast call.
        """
        if not self.enabled or not doc_text:
            return ""

        llm = self._get_fast_llm()
        if not llm:
            return ""

        try:
            preview = doc_text[:2500]
            prompt = DOC_SITUATE_PROMPT.format(document_preview=preview)
            res = llm.invoke(prompt)
            scope_text = re.sub(r"<.*?>", "", res.content).strip()
            # If valid short scope, return it
            if 10 < len(scope_text) < 300:
                return scope_text
        except Exception as err:
            logger.debug(f"Document scope extraction skipped (using deterministic): {err}")

        return ""

    def enrich_chunks(
        self,
        chunks: list[StructuredChunk],
        doc_text: str = "",
        doc_title: str = "",
        use_llm: bool = True,
    ) -> list[StructuredChunk]:
        """
        Enriches all retrievable chunks with contextual representations.
        Executes at most ONE fast call for the whole document, then applies
        O(1) deterministic situated context per chunk to eliminate 429 rate limits.
        """
        # 1. Single-pass global document scope (1 call max)
        doc_scope = ""
        if use_llm and self.enabled and doc_text:
            doc_scope = self.extract_document_situated_scope(doc_text, doc_title)

        # 2. Situating each chunk in O(1) time
        for chunk in chunks:
            det_prefix = self.generate_deterministic_context(chunk, doc_title)
            if doc_scope and chunk.content_type not in ("table", "figure"):
                context_rep = f"{det_prefix} Context: {doc_scope}"
            else:
                context_rep = det_prefix

            chunk.contextual_content = context_rep
            chunk.content = f"{context_rep}\n{chunk.raw_content}".strip()

        return chunks


# Singleton instance
_contextual_engine: Optional[ContextualRetrievalEngine] = None


def get_contextual_engine() -> ContextualRetrievalEngine:
    global _contextual_engine
    if _contextual_engine is None:
        _contextual_engine = ContextualRetrievalEngine()
    return _contextual_engine
