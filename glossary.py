"""
Ridge: Corpus-Aware Acronym & Entity Glossary Engine
====================================================
Extracts and maintains domain acronyms and entity definitions from ingested documents
to enrich query rewriting and hybrid retrieval recall.
"""

import json
import os
import re
from pathlib import Path

GLOSSARY_PATH = Path("./data/glossary.json")


def load_glossary() -> dict[str, dict]:
    """Loads the persistent glossary from disk."""
    if not GLOSSARY_PATH.exists():
        return {}
    try:
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Glossary load error: {e}")
        return {}


def save_glossary(glossary: dict[str, dict]) -> None:
    """Saves the glossary to disk."""
    GLOSSARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
            json.dump(glossary, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Glossary save error: {e}")


def extract_acronyms_from_text(text: str, source: str = "") -> dict[str, str]:
    """
    Extracts acronym definitions using regex heuristics:
    1. Full Expansion (ACRONYM)
    2. ACRONYM (Full Expansion)
    """
    found = {}
    if not text:
        return found

    # Pattern 1: Full Expansion (ACRONYM)
    # e.g., "Maximal Marginal Relevance (MMR)" or "Hierarchical Navigable Small World (HNSW)"
    p1 = re.finditer(r"\b((?:[A-Z][a-z0-9\-]+\s+){1,6}[A-Z][a-z0-9\-]+)\s*\(([A-Z0-9]{2,8})\)", text)
    for m in p1:
        expansion = m.group(1).strip()
        acronym = m.group(2).strip()
        words = [w for w in re.findall(r"\b[A-Za-z]", expansion) if w.isupper()]
        if len(words) >= len(acronym) - 1:
            found[acronym] = expansion

    # Pattern 2: ACRONYM (Full Expansion)
    # e.g., "PEAS (Performance, Environment, Actuators, Sensors)" or "CRAG (Corrective Retrieval-Augmented Generation)"
    p2 = re.finditer(r"\b([A-Z0-9]{2,8})\s*\(([A-Z][A-Za-z0-9\-,\s]{5,70})\)", text)
    for m in p2:
        acronym = m.group(1).strip()
        expansion = m.group(2).strip()
        if len(expansion.split()) >= 2:
            found[acronym] = expansion

    return found


def index_text_glossary(text: str, source: str = "") -> int:
    """Extracts acronyms from ingested text and updates the persistent glossary."""
    extracted = extract_acronyms_from_text(text, source)
    if not extracted:
        return 0

    current = load_glossary()
    added_count = 0
    for term, exp in extracted.items():
        if term not in current or current[term].get("expansion") != exp:
            current[term] = {
                "term": term,
                "expansion": exp,
                "source": source.split("/")[-1] if source else "Document Corpus"
            }
            added_count += 1

    if added_count > 0:
        save_glossary(current)
        print(f"  [Glossary] Indexed {added_count} domain acronyms from '{source}'")

    return added_count


def enrich_query_with_glossary(query: str) -> str:
    """Enriches a query by expanding known acronyms found in the corpus glossary."""
    glossary = load_glossary()
    if not glossary:
        return query

    words = re.findall(r"\b[A-Za-z0-9]{2,8}\b", query)
    expansions_added = []

    for w in words:
        upper_w = w.upper()
        if upper_w in glossary and upper_w not in expansions_added:
            exp = glossary[upper_w].get("expansion")
            if exp and exp.lower() not in query.lower():
                expansions_added.append(f"{upper_w} ({exp})")

    if expansions_added:
        return f"{query} [{' | '.join(expansions_added)}]"

    return query
