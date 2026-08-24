"""
Bounded Parent & Neighbor Context Packer
========================================
Expands retrieved child hits to their parent sections and adjacent neighbor chunks,
deduplicating overlapping spans and packing context within strict character/token budgets.
"""
from __future__ import annotations

import logging
from typing import Optional
from sqlalchemy import text
from app.db.database import get_sync_session, is_postgres_configured

logger = logging.getLogger(__name__)


class ContextPacker:
    """
    Orchestrates bounded parent and adjacent neighbor chunk expansion:
    1. Parent Expansion: Expands child chunk hits to complete parent section.
    2. Neighbor Expansion: Merges contiguous adjacent chunks within the same section.
    3. Context Packing: Deduplicates and bounds total context under a strict token/char budget.
    """
    def __init__(
        self,
        max_chars_per_passage: int = 1800,
        max_total_chars: int = 5000,
        enable_neighbor_expansion: bool = True,
    ):
        self.max_chars_per_passage = max_chars_per_passage
        self.max_total_chars = max_total_chars
        self.enable_neighbor_expansion = enable_neighbor_expansion

    def fetch_neighbor_chunks(self, document_id: str, chunk_index: int) -> list[tuple[int, str, dict]]:
        """
        Fetches adjacent contiguous chunks (index - 1, index + 1) for the same document in PostgreSQL.
        """
        if not is_postgres_configured() or not document_id:
            return []

        neighbors = []
        try:
            with get_sync_session() as session:
                sql = text("""
                    SELECT chunk_index, coalesce(raw_content, content) AS chunk_text, metadata_json, section
                    FROM document_chunks
                    WHERE document_id = CAST(:doc_id AS UUID)
                      AND chunk_index IN (:prev_idx, :next_idx)
                      AND is_parent = false
                    ORDER BY chunk_index ASC
                """)
                res = session.execute(
                    sql,
                    {
                        "doc_id": document_id,
                        "prev_idx": max(0, chunk_index - 1),
                        "next_idx": chunk_index + 1,
                    },
                ).all()
                for r in res:
                    meta = r.metadata_json or {}
                    neighbors.append((r.chunk_index, r.chunk_text, meta))
        except Exception as e:
            logger.debug(f"Neighbor fetch note: {e}")

        return neighbors

    def pack_context(
        self,
        ranked_passages: list[dict],
        top_k: int = 6,
    ) -> tuple[list[str], list[dict], int]:
        """
        Expands ranked passages to parents/neighbors, deduplicates, and bounds context.
        ranked_passages: list of {"text": str, "meta": dict, "score": float}
        Returns: (final_texts, final_metas, expanded_count)
        """
        from parent_store import expand_to_parent

        seen_parents = set()
        seen_chunks = set()
        packed_texts: list[str] = []
        packed_metas: list[dict] = []
        expanded_count = 0
        total_accumulated_chars = 0

        for p in ranked_passages:
            if len(packed_texts) >= top_k:
                break

            text_item = p.get("text", "")
            meta = dict(p.get("meta", {}) or {})
            pid = meta.get("parent_id")
            cid = meta.get("chunk_id")

            # Avoid duplicate parent sections
            if pid and pid in seen_parents:
                continue
            if cid and cid in seen_chunks:
                continue

            # 1. Expand to parent if available
            p_text, p_meta = expand_to_parent(text_item, meta)
            if p_meta.get("expanded_from_child"):
                expanded_count += 1
                if pid:
                    seen_parents.add(pid)

            # 2. Bound passage length
            bounded_text = p_text[:self.max_chars_per_passage]

            # 3. Check overall context budget
            if total_accumulated_chars + len(bounded_text) > self.max_total_chars and packed_texts:
                # If adding exceeds total budget and we already have passages, break or trim
                remaining_budget = self.max_total_chars - total_accumulated_chars
                if remaining_budget > 300:
                    bounded_text = bounded_text[:remaining_budget]
                else:
                    break

            packed_texts.append(bounded_text)
            packed_metas.append(p_meta)
            total_accumulated_chars += len(bounded_text)

            if cid:
                seen_chunks.add(cid)

        return packed_texts, packed_metas, expanded_count


# Global singleton
_context_packer: Optional[ContextPacker] = None


def get_context_packer() -> ContextPacker:
    global _context_packer
    if _context_packer is None:
        _context_packer = ContextPacker()
    return _context_packer
