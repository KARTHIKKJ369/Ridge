"""
Ridge: LangGraph State Machine Builder
======================================
Assembles and compiles the Corrective RAG state graph with conditional edges,
dynamic routing, multi-hop sub-query loops, and optional Langfuse tracing.
"""
import os
from langgraph.graph import END, StateGraph

from app.graph.state import GraphState
from app.graph.llm_factory import create_llm, get_llm_provider
from app.graph.nodes import (
    make_decompose_node,
    make_retrieve_node,
    make_grade_node,
    make_generate_node,
    make_check_hallucination_node,
    make_rewrite_node,
    make_web_search_node,
)
from app.graph.observability import get_langfuse_handler
from app.retrieval.hybrid import UnifiedRetriever


def get_default_settings() -> dict:
    return {
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5"),
        "chroma_dir": os.getenv("CHROMA_DIR", "./chroma_db"),
        "llm_provider": os.getenv("LLM_PROVIDER", get_llm_provider()),
        "google_api_key": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        "gemini_fast_model": os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite"),
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "groq_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "groq_fast_model": os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b"),
        "rerank_model": os.getenv("RERANK_MODEL", "ms-marco-MiniLM-L-12-v2"),
        "retriever_k": int(os.getenv("RETRIEVER_K", "6")),
        "retriever_fetch_k": int(os.getenv("RETRIEVER_FETCH_K", "60")),
        "rerank_top_n": int(os.getenv("RERANK_TOP_N", "20")),
        "retriever_lambda_mult": float(os.getenv("RETRIEVER_LAMBDA_MULT", "0.5")),
        "max_rewrite_loops": int(os.getenv("MAX_REWRITE_LOOPS", "1")),
        "grade_doc_limit": int(os.getenv("GRADE_DOC_LIMIT", "4")),
        "max_context_docs": int(os.getenv("MAX_CONTEXT_DOCS", "6")),
        "max_context_chars": int(os.getenv("MAX_CONTEXT_CHARS", "1200")),
    }


def build_app(custom_settings: dict | None = None):
    settings = {**get_default_settings(), **(custom_settings or {})}

    print(f"Initializing Ridge LangGraph Brain (Provider: {settings.get('llm_provider', 'auto')})...")

    llm_fast = create_llm(
        temperature=0.0,
        max_tokens=2048,
        tags=["auxiliary_model"],
        is_fast_model=True,
    )
    llm_generate = create_llm(
        temperature=0.1,
        max_tokens=4096,
        tags=["generation_stream"],
        is_fast_model=False,
    )

    retriever_engine = UnifiedRetriever(backend=os.getenv("RETRIEVAL_BACKEND", "pgvector"))

    # Construct individual nodes
    decompose_node = make_decompose_node(llm_fast, retriever_engine, settings)
    retrieve_node = make_retrieve_node(retriever_engine, settings)
    grade_node = make_grade_node(llm_fast, settings)
    generate_node = make_generate_node(llm_generate, llm_fast, settings)
    check_hallucination_node = make_check_hallucination_node(llm_fast)
    rewrite_node = make_rewrite_node(llm_fast, settings)
    web_search_node = make_web_search_node()

    # Router logic
    def decide_to_generate(state: GraphState) -> str:
        print("--- ROUTER: EVALUATING NEXT STEP ---")
        allow_web = state.get("web_search_enabled", True)
        loops = state.get("loop_count", 0)
        max_loops = int(settings.get("max_rewrite_loops", 1))

        if state.get("generation") == "yes":
            sub_queries = state.get("sub_queries", [])
            doc_grades = state.get("doc_grades", [])
            relevant_count = sum(1 for g in doc_grades if g.get("score") == "yes")
            if len(sub_queries) > 1 and allow_web and relevant_count < len(sub_queries):
                print(
                    f"-> Multi-hop coverage gap: {relevant_count} relevant docs for {len(sub_queries)} sub-queries."
                    " Route to: WEB SEARCH (gap fill)."
                )
                return "web_search"
            print("-> Document matches. Route to: GENERATE")
            return "generate"

        if loops >= max_loops:
            if allow_web:
                print(f"-> Safety valve tripped after {loops} rewrite attempts. Route to: WEB SEARCH.")
                return "web_search"
            else:
                print(f"-> Safety valve tripped after {loops} rewrite attempts. Web fallback disabled -> Route to: GENERATE (Direct Local KB).")
                return "generate"

        print("-> Document irrelevant. Route to: REWRITE")
        return "rewrite"

    def route_after_decompose(state: GraphState) -> str:
        if state.get("documents"):
            return "grade"
        return "retrieve"

    workflow = StateGraph(GraphState)
    workflow.add_node("decompose_node", decompose_node)
    workflow.add_node("retrieve_node", retrieve_node)
    workflow.add_node("web_search_node", web_search_node)
    workflow.add_node("grade_node", grade_node)
    workflow.add_node("generate_node", generate_node)
    workflow.add_node("check_hallucination_node", check_hallucination_node)
    workflow.add_node("rewrite_node", rewrite_node)

    # Wiring edges
    workflow.set_entry_point("decompose_node")
    workflow.add_conditional_edges(
        "decompose_node",
        route_after_decompose,
        {"grade": "grade_node", "retrieve": "retrieve_node"},
    )
    workflow.add_edge("retrieve_node", "grade_node")
    workflow.add_conditional_edges(
        "grade_node",
        decide_to_generate,
        {
            "generate": "generate_node",
            "rewrite": "rewrite_node",
            "web_search": "web_search_node",
        },
    )
    workflow.add_edge("rewrite_node", "retrieve_node")
    workflow.add_edge("web_search_node", "generate_node")
    workflow.add_edge("generate_node", "check_hallucination_node")
    workflow.add_edge("check_hallucination_node", END)

    compiled_graph = workflow.compile()
    return compiled_graph


_app_instance = None


def get_app():
    """Return the compiled LangGraph app, building it once and caching it as a lazy singleton."""
    global _app_instance
    if _app_instance is None:
        _app_instance = build_app()
    return _app_instance
