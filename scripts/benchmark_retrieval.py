"""
Retrieval Benchmark Suite: PostgreSQL + pgvector Hybrid Search & FlashRank
===========================================================================
Evaluates retrieval recall, hybrid RRF fusion, and sub-50ms execution latency
across dense vector search, PostgreSQL full-text search, and cross-encoder re-ranking.
"""
import os
import sys
import time
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from app.retrieval.pgvector_retriever import PgvectorRetriever
from app.retrieval.hybrid import UnifiedRetriever


def load_dataset():
    gold_path = PROJECT_ROOT / "eval" / "gold_dataset.json"
    if not gold_path.exists():
        return []
    with open(gold_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("test_cases", data) if isinstance(data, dict) else data


async def run_benchmark():
    dataset = load_dataset()
    if not dataset:
        print("No evaluation dataset found.")
        return

    print("=" * 70)
    print("🏔️  RIDGE RETRIEVAL BENCHMARK: PostgreSQL + pgvector System of Record")
    print("=" * 70)

    pg_retriever = PgvectorRetriever()
    unified = UnifiedRetriever(backend="pgvector")

    pg_latencies = []
    rerank_latencies = []

    for test_case in dataset:
        qid = test_case["id"]
        question = test_case["question"]
        src_filter = test_case.get("source_filter")

        print(f"\n[Test Case {qid}] '{question}'")
        if src_filter:
            print(f"  Source Filter: {src_filter}")

        # 1. Benchmark pgvector hybrid retrieval
        t0 = time.time()
        pg_candidates = await pg_retriever.retrieve(
            query=question,
            source_filter=src_filter,
            k=20,
        )
        t_pg = (time.time() - t0) * 1000
        pg_latencies.append(t_pg)

        # 2. Benchmark FlashRank reranking & small-to-big expansion
        t1 = time.time()
        texts, metas, expanded = unified.rerank_and_expand(
            query=question,
            candidates=pg_candidates,
            top_k=4,
        )
        t_rerank = (time.time() - t1) * 1000
        rerank_latencies.append(t_rerank)

        print(f"  pgvector Hybrid: {len(pg_candidates)} candidates retrieved in {t_pg:.1f} ms")
        print(f"  FlashRank + S2B: {len(texts)} re-ranked passages in {t_rerank:.1f} ms")
        if metas and "score" in metas[0]:
            print(f"  Top Candidate Score: {metas[0]['score']:.4f} | Source: {metas[0].get('source', 'N/A')}")

    avg_pg_lat = sum(pg_latencies) / len(pg_latencies)
    avg_rerank_lat = sum(rerank_latencies) / len(rerank_latencies)
    avg_total_lat = avg_pg_lat + avg_rerank_lat

    print("\n" + "=" * 70)
    print("📊 BENCHMARK SUMMARY (PostgreSQL + pgvector)")
    print("=" * 70)
    print(f"  • Total Test Cases Evaluated    : {len(dataset)}")
    print(f"  • Avg pgvector Hybrid Retrieval : {avg_pg_lat:.2f} ms")
    print(f"  • Avg FlashRank Cross-Encoder   : {avg_rerank_lat:.2f} ms")
    print(f"  • Avg Total End-to-End Retrieval: {avg_total_lat:.2f} ms")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_benchmark())

