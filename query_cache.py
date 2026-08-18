"""
query_cache.py — Semantic Vector Query Cache for Ridge
======================================================
Stores and retrieves previously answered queries using cosine similarity
over dense embeddings. If an incoming query has >= 0.96 cosine similarity
with a cached query, returns the verified cached answer in < 10ms.
"""

import json
import os
import time
from typing import Optional

CACHE_FILE_PATH = os.path.join("data", "query_cache.json")
DEFAULT_SIMILARITY_THRESHOLD = 0.96


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb + 1e-9)


def _load_cache() -> list[dict]:
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_cache(entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
    with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def get_cached_response(
    query: str,
    embedder,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    source_filter: Optional[str] = None
) -> Optional[dict]:
    """
    Checks if a semantically equivalent query already exists in the cache.
    Returns the cached response payload if cosine sim >= threshold, else None.
    """
    entries = _load_cache()
    if not entries:
        return None

    try:
        q_emb = embedder.embed_query(query)
    except Exception as e:
        print(f"  [QueryCache] Embedding error: {e}")
        return None

    best_match = None
    best_sim = -1.0

    for entry in entries:
        # Check source filter consistency
        entry_src = entry.get("source_filter")
        if source_filter and entry_src and source_filter != entry_src:
            continue

        c_emb = entry.get("embedding")
        if not c_emb:
            continue

        sim = _cosine_sim(q_emb, c_emb)
        if sim > best_sim:
            best_sim = sim
            best_match = entry

    if best_match and best_sim >= threshold:
        print(f"  ⚡ [QueryCache HIT] Match: '{best_match.get('question')}' (Cosine Sim: {best_sim:.4f})")
        res = dict(best_match)
        res["cache_hit"] = True
        res["similarity"] = round(best_sim, 4)
        return res

    return None


def store_cached_response(
    question: str,
    answer: str,
    confidence: dict,
    conflict_data: dict,
    embedder,
    source_filter: Optional[str] = None,
    max_entries: int = 500
) -> None:
    """
    Saves a verified high-confidence response into the persistent semantic cache.
    """
    if not question or not answer:
        return

    # Don't cache error responses or zero-coverage fallbacks
    if "could not find any relevant information" in answer.lower():
        return

    try:
        q_emb = embedder.embed_query(question)
    except Exception as e:
        print(f"  [QueryCache] Could not embed for store: {e}")
        return

    entries = _load_cache()

    # Deduplicate if exact or almost identical exists
    for e in entries:
        if e.get("question", "").strip().lower() == question.strip().lower():
            e["answer"] = answer
            e["confidence"] = confidence
            e["conflict_data"] = conflict_data
            e["embedding"] = q_emb
            e["updated_at"] = time.time()
            _save_cache(entries)
            return

    new_entry = {
        "question": question,
        "answer": answer,
        "confidence": confidence,
        "conflict_data": conflict_data,
        "source_filter": source_filter,
        "embedding": q_emb,
        "created_at": time.time()
    }
    entries.append(new_entry)

    # Keep within max size
    if len(entries) > max_entries:
        entries = entries[-max_entries:]

    _save_cache(entries)
    print(f"  [QueryCache] Stored query response in cache (Total cached: {len(entries)}).")
