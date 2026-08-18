"""
parent_store.py — Small-to-Big Retrieval: SQLite Parent Document Registry
=========================================================================
Stores full parent chunks (1500 chars) keyed by a stable parent_id.
Child chunks (400 chars) are indexed in Chroma with a parent_id reference.
At retrieval time, child hits are expanded back to their parent text.
Uses persistent SQLite for ACID compliance, zero file-rewrite latency, and concurrency.
"""

import json
import os
import sqlite3
import hashlib
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DB_PATH = Path(os.getenv("PARENT_STORE_DB_PATH", DATA_DIR / "parent_store.db"))
LEGACY_JSON_PATH = DATA_DIR / "parent_store.json"


def _get_conn() -> sqlite3.Connection:
    """Get a connection to the SQLite database and initialize tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parents (
            id       TEXT PRIMARY KEY,
            text     TEXT NOT NULL,
            metadata TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def _auto_migrate_legacy() -> None:
    """Migrate legacy data/parent_store.json records into SQLite if DB is empty."""
    if not LEGACY_JSON_PATH.exists():
        return
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM parents")
        count = cursor.fetchone()[0]
        if count == 0:
            with open(LEGACY_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                records = [
                    (pid, item.get("text", ""), json.dumps(item.get("metadata", {})))
                    for pid, item in data.items()
                ]
                cursor.executemany(
                    "INSERT OR REPLACE INTO parents (id, text, metadata) VALUES (?, ?, ?)",
                    records,
                )
                conn.commit()
                print(f"  [ParentStore] Migrated {len(records)} legacy parents from JSON to SQLite.")
        conn.close()
    except Exception as e:
        print(f"  [ParentStore] Legacy migration note: {e}")


# Run migration check on module import
_auto_migrate_legacy()


def make_parent_id(text: str, source: str) -> str:
    """Stable, short SHA-256 ID for a parent chunk."""
    digest = hashlib.sha256(f"{source}::{text[:300]}".encode()).hexdigest()
    return digest[:32]


def save_parents(parents: list[dict]) -> None:
    """
    Persist parent chunks to SQLite.
    parents: list of {"id": str, "text": str, "metadata": dict}
    """
    if not parents:
        return
    conn = _get_conn()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO parents (id, text, metadata) VALUES (?, ?, ?)",
            [(p["id"], p["text"], json.dumps(p.get("metadata", {}))) for p in parents],
        )
        conn.commit()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM parents")
        total = cursor.fetchone()[0]
        print(f"  [ParentStore] Saved {len(parents)} parent chunks (total: {total}).")
    finally:
        conn.close()


def expand_to_parent(child_text: str, child_meta: dict) -> tuple[str, dict]:
    """
    Given a child chunk, return (parent_text, parent_meta).
    Falls back to (child_text, child_meta) if no parent found.
    """
    pid = child_meta.get("parent_id")
    if not pid:
        return child_text, child_meta

    conn = _get_conn()
    try:
        row = conn.execute("SELECT text, metadata FROM parents WHERE id=?", (pid,)).fetchone()
        if row:
            parent_text = row[0]
            parent_meta = json.loads(row[1]) if row[1] else {}
            merged_meta = {**child_meta, **parent_meta, "expanded_from_child": True}
            return parent_text, merged_meta
    except Exception as e:
        print(f"  [ParentStore] Error looking up parent {pid}: {e}")
    finally:
        conn.close()

    return child_text, child_meta


def expand_documents(texts: list[str], metas: list[dict]) -> tuple[list[str], list[dict]]:
    """
    Expand a list of (child) retrieved documents to their parents.
    De-duplicates so the same parent is not returned twice.
    """
    seen_parents = set()
    expanded_texts = []
    expanded_metas = []

    # Batch query parent IDs for optimal performance
    pids_to_fetch = [m.get("parent_id") for m in metas if m.get("parent_id")]
    parents_map: dict[str, tuple[str, dict]] = {}

    if pids_to_fetch:
        conn = _get_conn()
        try:
            placeholders = ",".join("?" for _ in pids_to_fetch)
            cursor = conn.execute(
                f"SELECT id, text, metadata FROM parents WHERE id IN ({placeholders})",
                pids_to_fetch,
            )
            for row in cursor.fetchall():
                pid, text, meta_json = row
                try:
                    meta = json.loads(meta_json) if meta_json else {}
                except Exception:
                    meta = {}
                parents_map[pid] = (text, meta)
        except Exception as e:
            print(f"  [ParentStore] Batch expand error: {e}")
        finally:
            conn.close()

    for text, meta in zip(texts, metas):
        pid = meta.get("parent_id")
        if pid and pid in seen_parents:
            continue

        if pid and pid in parents_map:
            p_text, p_meta = parents_map[pid]
            merged_meta = {**meta, **p_meta, "expanded_from_child": True}
            expanded_texts.append(p_text)
            expanded_metas.append(merged_meta)
            seen_parents.add(pid)
        else:
            expanded_texts.append(text)
            expanded_metas.append(meta)
            if pid:
                seen_parents.add(pid)

    return expanded_texts, expanded_metas
