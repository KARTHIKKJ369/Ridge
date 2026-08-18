"""
parent_store.py — Small-to-Big Retrieval: Parent Document Registry
==================================================================
Stores full parent chunks (1500 chars) keyed by a stable parent_id.
Child chunks (400 chars) are indexed in Chroma with a parent_id reference.
At retrieval time, child hits are expanded back to their parent text.
"""

import json
import os
import hashlib

PARENT_STORE_PATH = os.path.join("data", "parent_store.json")


def _load() -> dict:
    if os.path.exists(PARENT_STORE_PATH):
        try:
            with open(PARENT_STORE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save(store: dict) -> None:
    os.makedirs(os.path.dirname(PARENT_STORE_PATH), exist_ok=True)
    with open(PARENT_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def make_parent_id(text: str, source: str) -> str:
    """Stable, short SHA-256 ID for a parent chunk."""
    digest = hashlib.sha256(f"{source}::{text[:300]}".encode()).hexdigest()
    return digest[:20]


def save_parents(parents: list) -> None:
    """
    Persist parent chunks.
    parents: list of {"id": str, "text": str, "metadata": dict}
    """
    store = _load()
    for p in parents:
        store[p["id"]] = {"text": p["text"], "metadata": p["metadata"]}
    _save(store)
    print(f"  [ParentStore] Saved {len(parents)} parent chunks (total: {len(store)}).")


def expand_to_parent(child_text: str, child_meta: dict):
    """
    Given a child chunk, return (parent_text, parent_meta).
    Falls back to (child_text, child_meta) if no parent found.
    """
    pid = child_meta.get("parent_id")
    if not pid:
        return child_text, child_meta

    store = _load()
    entry = store.get(pid)
    if entry:
        merged_meta = {**child_meta, **entry.get("metadata", {}), "expanded_from_child": True}
        return entry["text"], merged_meta

    return child_text, child_meta


def expand_documents(texts: list, metas: list):
    """
    Expand a list of (child) retrieved documents to their parents.
    De-duplicates so the same parent is not returned twice.
    """
    seen_parents = set()
    expanded_texts = []
    expanded_metas = []

    for text, meta in zip(texts, metas):
        pid = meta.get("parent_id")
        # If this child's parent was already added, skip
        if pid and pid in seen_parents:
            continue

        exp_text, exp_meta = expand_to_parent(text, meta)
        expanded_texts.append(exp_text)
        expanded_metas.append(exp_meta)

        if pid:
            seen_parents.add(pid)

    return expanded_texts, expanded_metas
