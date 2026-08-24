"""
Deduplication & Boilerplate Filtering Engine
============================================
Implements exact SHA-256 hashing, 64-bit SimHash near-duplicate detection,
and cross-page boilerplate/header/footer pattern recognition.
"""
from __future__ import annotations

import re
import hashlib
from typing import Optional
from app.document_intelligence.chunker import StructuredChunk


class SimHasher:
    """
    Computes 64-bit SimHash fingerprints for near-duplicate text detection.
    Hamming distance <= 3 indicates near-identical text (e.g., minor typo or timestamp difference).
    """
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        words = re.findall(r"\w+", text.lower())
        tokens = list(words)
        for i in range(len(words) - 1):
            tokens.append(f"{words[i]}_{words[i+1]}")
        return tokens


    @classmethod
    def fingerprint(cls, text: str) -> int:
        tokens = cls._tokenize(text)
        if not tokens:
            return 0

        v = [0] * 64
        for token in tokens:
            # 64-bit hash of token
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:16], 16)
            for i in range(64):
                bit = (h >> i) & 1
                v[i] += 1 if bit else -1

        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= (1 << i)
        return fingerprint

    @staticmethod
    def hamming_distance(fp1: int, fp2: int) -> int:
        """Counts the number of differing bits between two 64-bit fingerprints."""
        x = fp1 ^ fp2
        dist = 0
        while x:
            dist += 1
            x &= x - 1
        return dist


class BoilerplateDetector:
    """
    Detects recurring headers, footers, copyright notices, and page numbering patterns.
    """
    BOILERPLATE_PATTERNS = [
        re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE),
        re.compile(r"^confidential\s+-\s+.*", re.IGNORECASE),
        re.compile(r"^(all\s+rights\s+reserved|copyright\s+©?\s*\d{4}).*", re.IGNORECASE),
        re.compile(r"^(privacy\s+policy|terms\s+of\s+service|cookie\s+settings).*", re.IGNORECASE),
        re.compile(r"^table\s+of\s+contents$", re.IGNORECASE),
    ]

    @classmethod
    def is_boilerplate(cls, text: str) -> bool:
        clean = text.strip().lower()
        if len(clean) < 15:
            # Very short text that looks like a page number or artifact
            if re.match(r"^(\d+|page\s*\d+)$", clean):
                return True

        for pattern in cls.BOILERPLATE_PATTERNS:
            if pattern.match(clean):
                return True
        return False


class Deduplicator:
    """
    Orchestrates exact and near-duplicate filtering across chunks within an ingestion run.
    """
    def __init__(self, near_dup_threshold: int = 3):
        self.near_dup_threshold = near_dup_threshold

    def deduplicate_chunks(
        self,
        chunks: list[StructuredChunk],
    ) -> tuple[list[StructuredChunk], int]:
        """
        Processes chunks, marking duplicate/boilerplate chunks while preserving primary records.
        Returns: (clean_chunks, dedup_removed_count)
        """
        seen_exact_hashes: dict[str, str] = {}  # sha256 -> chunk_id
        seen_simhashes: dict[int, str] = {}     # simhash -> chunk_id
        clean_chunks: list[StructuredChunk] = []
        dedup_count = 0

        for chunk in chunks:
            raw_text = chunk.raw_content.strip()
            if not raw_text:
                continue

            # 1. Check Boilerplate
            if BoilerplateDetector.is_boilerplate(raw_text):
                chunk.metadata["is_boilerplate"] = True
                dedup_count += 1
                continue

            # 2. Check Exact Duplicate (SHA-256)
            norm_text = re.sub(r"\s+", " ", raw_text.lower())
            sha = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()

            if sha in seen_exact_hashes:
                chunk.metadata["duplicate_of"] = seen_exact_hashes[sha]
                dedup_count += 1
                continue
            seen_exact_hashes[sha] = chunk.id

            # 3. Check Near Duplicate (SimHash)
            if len(raw_text) >= 60:
                fp = SimHasher.fingerprint(raw_text)
                is_near_dup = False
                for existing_fp, existing_id in seen_simhashes.items():
                    if SimHasher.hamming_distance(fp, existing_fp) <= self.near_dup_threshold:
                        chunk.metadata["duplicate_of"] = existing_id
                        chunk.metadata["near_duplicate"] = True
                        dedup_count += 1
                        is_near_dup = True
                        break

                if is_near_dup:
                    continue
                seen_simhashes[fp] = chunk.id

            clean_chunks.append(chunk)

        return clean_chunks, dedup_count


# Global singleton
_deduplicator: Optional[Deduplicator] = None


def get_deduplicator() -> Deduplicator:
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = Deduplicator()
    return _deduplicator
