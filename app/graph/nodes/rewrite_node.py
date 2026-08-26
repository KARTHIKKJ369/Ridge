"""
Ridge: Query Rewrite & Domain Expansion Node
============================================
Optimizes and reformulates technical search queries that yielded low relevance,
enriching the query with domain acronym definitions from the knowledge glossary.
"""
import time
from typing import Callable
from langchain_core.language_models.chat_models import BaseChatModel

from app.graph.state import GraphState
from app.graph.prompts import clean_llm_response


def make_rewrite_node(
    llm_fast: BaseChatModel,
    settings: dict,
) -> Callable[[GraphState], dict]:

    def rewrite_node(state: GraphState) -> dict:
        t0 = time.time()
        print("--- NODE: REWRITE QUERY ---")
        original_q = state.get("original_question") or state["question"]
        current_loops = state.get("loop_count", 0) + 1
        past_queries = state.get("past_queries", [])

        prompt = (
            "You are a search query optimizer for a technical retriever.\n"
            f"Original user question: {original_q}\n"
            f"Previous attempts that had no matches: {past_queries}\n\n"
            "Generate a single, focused 3 to 6 word search query.\n"
            "Do NOT repeat words or output long repetitive lists.\n"
            "Output ONLY the plain search query string."
        )

        new_query = None
        try:
            response = llm_fast.invoke(prompt)
            cleaned = clean_llm_response(response.content)
            candidate_lines = []
            for line in cleaned.split("\n"):
                line_str = line.strip().replace("`", "").replace('"', "").replace("*", "").replace("#", "")
                if not line_str:
                    continue
                if any(skip_kw in line_str.lower() for skip_kw in ["thinking process", "process:", "analyze", "here's", "<", "search query:", "reformulated:", "user question"]):
                    continue
                candidate_lines.append(line_str)
            if candidate_lines:
                new_query = candidate_lines[-1]
        except Exception as e:
            print(f"  rewrite attempt failed: {e}")

        if not new_query or len(new_query) < 3 or new_query.startswith("<"):
            new_query = original_q

        # Enrich query with domain acronym expansions from glossary
        try:
            from glossary import enrich_query_with_glossary
            source_filter = state.get("source_filter")
            active_srcs = {source_filter} if source_filter else None
            user_id = state.get("user_id")
            new_query = enrich_query_with_glossary(new_query, active_sources=active_srcs, user_id=user_id)
        except Exception as ge:
            print(f"Glossary query enrichment note: {ge}")

        print(f"New Search Query: '{new_query}'")
        print(f"Current Loop Counter: {current_loops}/{settings.get('max_rewrite_loops', 1)}")

        return {
            "question": new_query,
            "original_question": original_q,
            "loop_count": current_loops,
            "past_queries": past_queries + [new_query],
            "latency_ms": int((time.time() - t0) * 1000),
        }

    return rewrite_node
