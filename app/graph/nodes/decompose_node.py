"""
Ridge: Query Decomposition Node (Multi-Hop)
===========================================
Detects compound/multi-part questions, decomposes into focused sub-queries,
and executes parallel hybrid retrieval with candidate de-duplication.
"""
import time
import json
import re
import uuid
import asyncio
from typing import Callable
from langchain_core.language_models.chat_models import BaseChatModel

from app.graph.state import GraphState
from app.graph.prompts import clean_llm_response
from app.retrieval.interface import BaseRetriever


COMPOUND_SIGNALS = [
    " and ", " also ", " compare ", " vs ", " versus ",
    " as well as ", " both ", " additionally ", " furthermore ", " difference between "
]


def _looks_compound(q: str) -> bool:
    q_lower = q.lower()
    return any(sig in q_lower for sig in COMPOUND_SIGNALS)


def make_decompose_node(
    llm_fast: BaseChatModel,
    retriever_engine: BaseRetriever,
    settings: dict,
) -> Callable[[GraphState], asyncio.Future]:

    async def decompose_node(state: GraphState) -> dict:
        """Detect compound/multi-part questions, split into focused sub-queries,
        run parallel hybrid retrieval for each, and merge results via RRF."""
        t0 = time.time()
        question = state["question"]
        tenant_id = state.get("tenant_id")
        t_uuid = uuid.UUID(tenant_id) if tenant_id else None
        print("\n--- NODE: QUERY DECOMPOSITION ---")

        # Skip LLM call entirely for clearly simple questions
        if not _looks_compound(question):
            print("  [Decompose] Simple question (heuristic). Skipping LLM decomposition.")
            return {"sub_queries": [question], "latency_ms": 0}

        # --- Step 1: Detect if question is compound via LLM ---
        detect_prompt = (
            "You are a query analysis assistant.\n"
            f"User question: {question}\n\n"
            "Determine if this question contains MULTIPLE distinct parts or asks about MULTIPLE"
            " separate topics that each require independent retrieval.\n"
            "Examples of compound: 'Compare PEAS and DECIDE frameworks, and also explain BFS vs DFS'\n"
            "Examples of simple: 'What is PEAS?', 'How does BFS work?'\n\n"
            "If compound, decompose into 2-4 concise, focused sub-queries.\n"
            "If simple, return the original question as the only sub-query.\n"
            "Return ONLY valid JSON: {\"compound\": true|false, \"sub_queries\": [\"q1\", ...]}"
        )
        sub_queries = [question]  # default: no decomposition
        try:
            resp = await llm_fast.ainvoke(detect_prompt)
            cleaned = clean_llm_response(resp.content)
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                if data.get("compound") and data.get("sub_queries"):
                    candidates_q = [str(q).strip() for q in data["sub_queries"] if q and len(str(q).strip()) > 3]
                    if len(candidates_q) >= 2:
                        sub_queries = candidates_q[:4]
                        print(f"  Compound question detected. Sub-queries: {sub_queries}")
                    else:
                        print("  Simple question detected. No decomposition needed.")
                else:
                    print("  Simple question detected. No decomposition needed.")
        except Exception as e:
            print(f"  Decomposition note: {e}")

        if len(sub_queries) == 1:
            return {"sub_queries": sub_queries, "latency_ms": int((time.time() - t0) * 1000)}

        # Parallel hybrid retrieval across all sub-queries simultaneously
        all_candidates = []
        try:
            results = await asyncio.gather(
                *[
                    retriever_engine.retrieve(
                        query=sq,
                        user_id=state.get("user_id"),
                        tenant_id=t_uuid,
                        source_filter=state.get("source_filter"),
                        k=settings.get("retriever_fetch_k", 60),
                    )
                    for sq in sub_queries
                ],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    print(f"  [Decompose Node] Sub-query retrieval error: {r}")
                else:
                    all_candidates.extend(r)
        except Exception as dec_err:
            print(f"  [Decompose Node] Warning: parallel retrieval failed ({dec_err}), proceeding with empty results.")

        # De-duplicate candidates by chunk_id or text
        seen_chunks = set()
        unique_candidates = []
        for c in all_candidates:
            key = c.chunk_id or c.text.strip()[:100]
            if key not in seen_chunks:
                seen_chunks.add(key)
                unique_candidates.append(c)

        final_texts, final_metas, expanded_count = retriever_engine.rerank_and_expand(
            query=question,
            candidates=unique_candidates,
            top_k=settings.get("retriever_k", 6),
            rerank_top_n=settings.get("rerank_top_n", 20),
        )

        return {
            "sub_queries": sub_queries,
            "documents": final_texts,
            "documents_metadata": final_metas,
            "expanded_count": expanded_count,
            "latency_ms": int((time.time() - t0) * 1000),
        }

    return decompose_node
