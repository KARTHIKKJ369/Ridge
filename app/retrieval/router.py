"""
Query-Aware Retrieval Intent Router
===================================
Classifies queries into retrieval archetypes (EXACT, TABULAR, SEMANTIC, SUMMARY, MULTI_HOP)
and dynamically tailors retrieval parameters, scoring weights, and candidate filtering.
"""
from __future__ import annotations

import re
from enum import Enum
from pydantic import BaseModel, Field


class QueryArchetype(str, Enum):
    EXACT = "exact_lookup"          # Exact keywords, acronyms, IDs, code symbols
    TABULAR = "tabular_numeric"     # Quantitative metrics, financial tables, columns
    SEMANTIC = "semantic_concept"   # Explanatory, conceptual, how-to, why
    SUMMARY = "global_summary"      # Broad overviews, summaries, document scope
    MULTI_HOP = "multi_hop_compare" # Comparative, multi-entity synthesis


class RetrievalPlan(BaseModel):
    """Execution parameters tailored to the detected query archetype."""
    archetype: QueryArchetype
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    prioritize_tables: bool = False
    prioritize_summaries: bool = False
    top_k_candidates: int = 50
    rerank_top_n: int = 20
    reasoning: str = ""


class QueryIntentRouter:
    """
    Sub-millisecond rule-based classifier with archetype pattern matching.
    """
    SUMMARY_PATTERNS = [
        re.compile(r"^(summarize|summary|overview|give an overview|what is (this|the) (document|paper|report|guide) about)", re.IGNORECASE),
        re.compile(r"(executive summary|high-level summary|tldr)", re.IGNORECASE),
    ]

    TABULAR_PATTERNS = [
        re.compile(r"\b(revenue|margin|ebitda|growth|q[1-4]|table|breakdown|statistics|percentage|cost|budget|metric)\b", re.IGNORECASE),
        re.compile(r"(\$|\%|\d+\s*(million|billion|k|m|b))", re.IGNORECASE),
    ]

    MULTI_HOP_PATTERNS = [
        re.compile(r"\b(compare|difference between|versus|vs\.?|pros and cons|how does .* compare to)\b", re.IGNORECASE),
        re.compile(r"\b(both .* and|relationship between)\b", re.IGNORECASE),
    ]

    EXACT_PATTERNS = [
        re.compile(r"^[A-Z0-9_\-\.]{2,15}$"),  # Acronyms or symbol names (e.g. DSU, HNSW, RRF, API)
        re.compile(r"\b(define|acronym|abbreviation|symbol|function|endpoint|error code)\b", re.IGNORECASE),
        re.compile(r"['\"`][^'\"]+['\"`]"),     # Quoted exact phrases
    ]

    @classmethod
    def route_query(cls, query: str) -> RetrievalPlan:
        q = query.strip()

        # 1. Check Global Summarization
        for pat in cls.SUMMARY_PATTERNS:
            if pat.search(q):
                return RetrievalPlan(
                    archetype=QueryArchetype.SUMMARY,
                    dense_weight=0.6,
                    sparse_weight=0.4,
                    prioritize_summaries=True,
                    top_k_candidates=40,
                    rerank_top_n=15,
                    reasoning="Detected global document summary intent.",
                )

        # 2. Check Tabular / Numeric
        for pat in cls.TABULAR_PATTERNS:
            if pat.search(q):
                return RetrievalPlan(
                    archetype=QueryArchetype.TABULAR,
                    dense_weight=0.4,
                    sparse_weight=0.6,
                    prioritize_tables=True,
                    top_k_candidates=50,
                    rerank_top_n=25,
                    reasoning="Detected quantitative/tabular metric lookup intent.",
                )

        # 3. Check Multi-Hop / Comparison
        for pat in cls.MULTI_HOP_PATTERNS:
            if pat.search(q):
                return RetrievalPlan(
                    archetype=QueryArchetype.MULTI_HOP,
                    dense_weight=0.6,
                    sparse_weight=0.4,
                    top_k_candidates=60,
                    rerank_top_n=30,
                    reasoning="Detected multi-entity comparative analysis intent.",
                )

        # 4. Check Exact / Lookup
        for pat in cls.EXACT_PATTERNS:
            if pat.search(q):
                return RetrievalPlan(
                    archetype=QueryArchetype.EXACT,
                    dense_weight=0.3,
                    sparse_weight=0.7,
                    top_k_candidates=50,
                    rerank_top_n=20,
                    reasoning="Detected exact keyword/acronym lookup intent.",
                )

        # 5. Default to Balanced Semantic Concept
        return RetrievalPlan(
            archetype=QueryArchetype.SEMANTIC,
            dense_weight=0.55,
            sparse_weight=0.45,
            top_k_candidates=50,
            rerank_top_n=20,
            reasoning="Defaulted to balanced semantic hybrid retrieval.",
        )


# Global singleton
_router: Optional[QueryIntentRouter] = None


def get_query_router() -> QueryIntentRouter:
    global _router
    if _router is None:
        _router = QueryIntentRouter()
    return _router
