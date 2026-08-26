"""
Tests for Phase 4 & 5: Retrieval Engines & Hybrid RRF
"""
import pytest
from app.retrieval.pgvector_retriever import PgvectorRetriever
from app.retrieval.hybrid import UnifiedRetriever



@pytest.mark.asyncio
async def test_pgvector_retriever_hybrid_search():
    retriever = PgvectorRetriever()
    query = "What is task decomposition in LLM agents?"
    
    candidates = await retriever.retrieve(query=query, k=10)
    assert len(candidates) > 0
    top = candidates[0]
    assert top.text is not None
    assert top.rrf_score > 0.0
    assert "source" in top.metadata


@pytest.mark.asyncio
async def test_unified_retriever_pgvector_mode():
    retriever = UnifiedRetriever(backend="pgvector")
    query = "What is task decomposition in LLM agents?"

    
    candidates = await retriever.retrieve(query=query, k=10)
    assert len(candidates) > 0

    texts, metas, expanded = retriever.rerank_and_expand(
        query=query,
        candidates=candidates,
        top_k=4,
    )
    assert len(texts) > 0
    assert len(metas) == len(texts)
    assert "score" in metas[0]


@pytest.mark.asyncio
async def test_source_filtering():
    from main import aingest_document
    await aingest_document(
        text_or_url="Graph neural networks (GNNs) analyze complex relational graphs and structured data.",
        original_filename="gnn_research_paper.pdf",
        user_id="test_user",
        is_shared=True,
    )

    retriever = PgvectorRetriever()
    query = "graph neural network"
    
    # Filter by specific source
    candidates = await retriever.retrieve(
        query=query,
        source_filter="gnn_research_paper.pdf",
        k=5,
    )
    assert len(candidates) > 0
    for c in candidates:
        assert "gnn_research_paper.pdf" in c.metadata.get("source", "")
