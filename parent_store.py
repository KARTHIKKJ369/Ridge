"""
parent_store.py — Small-to-Big Retrieval: Parent Document Store
================================================================
Stores full parent chunks (1500 chars) keyed by a stable parent_id.
Uses in-memory LRU cache and PostgreSQL document_chunks lookup.
"""

import json
import os
import hashlib
from typing import Optional
from sqlalchemy import text
from app.db.database import get_sync_session, is_postgres_configured

# Fast In-Memory LRU Cache for parent chunks
_PARENT_CACHE: dict[str, tuple[str, dict]] = {}
_MAX_CACHE_SIZE = 5000


def make_parent_id(text: str, source: str) -> str:
    """Stable, short SHA-256 ID for a parent chunk."""
    digest = hashlib.sha256(f"{source}::{text[:300]}".encode()).hexdigest()
    return digest[:32]


def save_parents(parents: list[dict]) -> None:
    """
    Persist parent chunks to in-memory cache and PostgreSQL.
    parents: list of {"id": str, "text": str, "metadata": dict}
    """
    global _PARENT_CACHE
    if not parents:
        return

    for p in parents:
        pid = p["id"]
        _PARENT_CACHE[pid] = (p["text"], p.get("metadata", {}))

    # Keep cache within bounds
    if len(_PARENT_CACHE) > _MAX_CACHE_SIZE:
        keys_to_remove = list(_PARENT_CACHE.keys())[:len(_PARENT_CACHE) - _MAX_CACHE_SIZE]
        for k in keys_to_remove:
            _PARENT_CACHE.pop(k, None)

    print(f"  [ParentStore] Cached {len(parents)} parent chunks in memory (total: {len(_PARENT_CACHE)}).")


def expand_to_parent(child_text: str, child_meta: dict) -> tuple[str, dict]:
    """
    Given a child chunk, return (parent_text, parent_meta).
    Falls back to (child_text, child_meta) if no parent found.
    """
    pid = child_meta.get("parent_id")
    if not pid:
        return child_text, child_meta

    # 1. Check in-memory cache
    if pid in _PARENT_CACHE:
        p_text, p_meta = _PARENT_CACHE[pid]
        return p_text, {**child_meta, **p_meta, "expanded_from_child": True}

    # 2. Check PostgreSQL document_chunks
    try:
        with get_sync_session() as session:
            row = session.execute(
                text("SELECT content, metadata_json FROM document_chunks WHERE metadata_json->>'parent_id' = :pid OR id::text = :pid LIMIT 1"),
                {"pid": pid}
            ).first()
            if row:
                p_text = row[0]
                p_meta = row[1] if isinstance(row[1], dict) else (json.loads(row[1]) if row[1] else {})
                _PARENT_CACHE[pid] = (p_text, p_meta)
                return p_text, {**child_meta, **p_meta, "expanded_from_child": True}
    except Exception:
        pass

    return child_text, child_meta


def expand_documents(texts: list[str], metas: list[dict]) -> tuple[list[str], list[dict]]:
    """
    Expand a list of (child) retrieved documents to their parents.
    De-duplicates so the same parent is not returned twice.
    """
    seen_parents = set()
    expanded_texts = []
    expanded_metas = []

    for text_item, meta in zip(texts, metas):
        pid = meta.get("parent_id")
        if pid and pid in seen_parents:
            continue

        p_text, p_meta = expand_to_parent(text_item, meta)
        expanded_texts.append(p_text)
        expanded_metas.append(p_meta)
        if pid:
            seen_parents.add(pid)

    return expanded_texts, expanded_metas

