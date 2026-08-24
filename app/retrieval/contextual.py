"""
Anthropic-Style Contextual Retrieval Engine
===========================================
Generates 50–100 token situated contextual representations for retrievable chunks,
positioning each chunk within the global context of its parent document.
Provides fast LLM contextualization with deterministic hierarchy fallbacks.
"""
from __future__ import annotations

import os
import re
import logging
from typing import Optional

from app.document_intelligence.chunker import StructuredChunk

logger = logging.getLogger(__name__)

CONTEXTUAL_PROMPT_TEMPLATE = """<document>
{document_text}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_text}
</chunk>

Please give a short, succinct context (1-2 sentences, maximum 60 words) to situate this chunk within the overall document for search retrieval. Mention the document subject, entity names, dates/years, or section topic if applicable.
Answer only with the succinct context description:"""


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
                from main import get_settings
                from langchain_groq import ChatGroq

                settings = get_settings()
                if settings.get("groq_api_key"):
                    self._llm = ChatGroq(
                        api_key=settings["groq_api_key"],
                        model_name=settings.get("groq_fast_model", "openai/gpt-oss-20b"),
                        temperature=0.2,
                        max_tokens=128,
                    )
            except Exception as e:
                logger.warning(f"Fast LLM initialization note for Contextual Retrieval: {e}")
        return self._llm

    def generate_deterministic_context(self, chunk: StructuredChunk, doc_title: str = "") -> str:
        """
        Fast deterministic fallback: constructs situated context from document title,
        section breadcrumbs, page numbers, and structural element types.
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

        return f"[{' | '.join(parts)}]"

    def contextualize_chunk(
        self,
        doc_preview: str,
        chunk: StructuredChunk,
        doc_title: str = "",
        use_llm: bool = True,
    ) -> str:
        """
        Generates situated context for a single chunk via LLM or deterministic fallback.
        """
        deterministic_prefix = self.generate_deterministic_context(chunk, doc_title)

        if not self.enabled or not use_llm:
            return deterministic_prefix

        llm = self._get_fast_llm()
        if not llm:
            return deterministic_prefix

        try:
            # Truncate doc preview if giant to avoid latency
            preview = doc_preview[:3000] if len(doc_preview) > 3000 else doc_preview
            prompt = CONTEXTUAL_PROMPT_TEMPLATE.format(
                document_text=preview,
                chunk_text=chunk.raw_content[:800],
            )
            response = llm.invoke(prompt)
            llm_text = response.content.strip()
            # Clean reasoning or tag artifacts
            llm_text = re.sub(r"<.*?>", "", llm_text).strip()
            if llm_text:
                return f"{deterministic_prefix} {llm_text}"
        except Exception as err:
            logger.warning(f"LLM Contextualization fallback on chunk: {err}")

        return deterministic_prefix

    def enrich_chunks(
        self,
        chunks: list[StructuredChunk],
        doc_text: str = "",
        doc_title: str = "",
        use_llm: bool = True,
    ) -> list[StructuredChunk]:
        """
        Enriches all retrievable chunks with contextual representations.
        Sets chunk.contextual_content and updates chunk.content for vector embedding.
        """
        for chunk in chunks:
            # Generate situated context
            context_prefix = self.contextualize_chunk(
                doc_preview=doc_text,
                chunk=chunk,
                doc_title=doc_title,
                use_llm=use_llm,
            )
            chunk.contextual_content = context_prefix
            # Update search representation with situated context + raw content
            chunk.content = f"{context_prefix}\n{chunk.raw_content}".strip()

        return chunks


# Singleton instance
_contextual_engine: Optional[ContextualRetrievalEngine] = None


def get_contextual_engine() -> ContextualRetrievalEngine:
    global _contextual_engine
    if _contextual_engine is None:
        _contextual_engine = ContextualRetrievalEngine()
    return _contextual_engine
