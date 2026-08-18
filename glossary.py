"""
Ridge: Corpus-Aware Acronym & Entity Glossary Engine
====================================================
Extracts and maintains domain acronyms and entity definitions from ingested documents
to enrich query rewriting and hybrid retrieval recall. Supports multi-tenant scoping,
per-source document lifecycle synchronization, and precise initialism validation.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

GLOSSARY_PATH = Path(os.getenv("GLOSSARY_PATH", "./data/glossary.json"))

# Stop words stripped from acronym expansion prefixes
STOP_PREFIXES = {
    "the", "a", "an", "using", "list", "in", "with", "for", "and", "by", 
    "on", "from", "to", "of", "our", "their", "this", "that"
}


def load_glossary() -> dict[str, dict]:
    """Loads the persistent glossary from disk."""
    if not GLOSSARY_PATH.exists():
        return {}
    try:
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
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


def clean_expansion(exp: str) -> str:
    """Cleans up raw expansion text by normalizing whitespace and stripping leading stop words."""
    if not exp:
        return ""
    # Normalize internal whitespace and newlines
    cleaned = re.sub(r"\s+", " ", exp).strip()
    words = cleaned.split(" ")
    while words and words[0].lower() in STOP_PREFIXES:
        words.pop(0)
    return " ".join(words).strip(" ,;:-()")


def is_valid_acronym_match(acronym: str, expansion: str) -> bool:
    """
    Validates whether an acronym corresponds plausibly to the expansion string.
    Filters out noisy false positives (e.g. author bios, random parenthesized text).
    """
    acronym = acronym.strip().upper()
    expansion_clean = clean_expansion(expansion)
    if not acronym or not expansion_clean or len(acronym) < 2 or len(acronym) > 8:
        return False
    if acronym.lower() == expansion_clean.lower():
        return False

    # Extract significant words
    words = [w for w in re.split(r"[\s\-/,]+", expansion_clean) if w]
    words_sig = [w for w in words if w.lower() not in STOP_PREFIXES]
    if not words_sig:
        words_sig = words

    initials = "".join(w[0].upper() for w in words_sig if w)

    # 1. Exact initials match
    if acronym == initials:
        return True

    # 2. Number / hybrid acronyms (e.g. Ground-to-air -> G2A, 6G)
    if any(c.isdigit() for c in acronym):
        if initials and acronym[0] == initials[0]:
            return True

    # 3. Subsequence alignment check: characters of acronym must appear in order in initials
    matching_chars = 0
    init_idx = 0
    for char in acronym:
        pos = initials.find(char, init_idx)
        if pos != -1:
            matching_chars += 1
            init_idx = pos + 1

    ratio = matching_chars / len(acronym)
    return ratio >= 0.75


def extract_acronyms_from_text(text: str, source: str = "") -> dict[str, str]:
    """
    Extracts high-precision acronym definitions using regex heuristics:
    1. Full Expansion (ACRONYM)
    2. ACRONYM (Full Expansion)
    """
    found = {}
    if not text:
        return found

    # Normalize text whitespace slightly to allow cross-newline capture
    normalized_text = re.sub(r"[ \t]+", " ", text)

    # Pattern 1: Full Expansion (ACRONYM)
    # e.g., "Maximal Marginal Relevance (MMR)" or "Hierarchical Navigable Small World (HNSW)"
    p1 = re.finditer(r"\b((?:[A-Z][a-z0-9\-]+\s+){1,6}[A-Z][a-z0-9\-]+)\s*\(([A-Z0-9]{2,8})\)", normalized_text)
    for m in p1:
        expansion_raw = m.group(1).strip()
        acronym = m.group(2).strip().upper()
        expansion = clean_expansion(expansion_raw)
        if is_valid_acronym_match(acronym, expansion):
            found[acronym] = expansion

    # Pattern 2: ACRONYM (Full Expansion)
    # e.g., "PEAS (Performance, Environment, Actuators, Sensors)" or "CRAG (Corrective Retrieval-Augmented Generation)"
    p2 = re.finditer(r"\b([A-Z0-9]{2,8})\s*\(([A-Z][A-Za-z0-9\-,\s]{5,70})\)", normalized_text)
    for m in p2:
        acronym = m.group(1).strip().upper()
        expansion_raw = m.group(2).strip()
        expansion = clean_expansion(expansion_raw)
        if len(expansion.split()) >= 2 and is_valid_acronym_match(acronym, expansion):
            found[acronym] = expansion

    return found


def index_text_glossary(text: str, source: str = "", user_id: str = "default") -> int:
    """Extracts acronyms from ingested text and updates the persistent glossary."""
    extracted = extract_acronyms_from_text(text, source)
    if not extracted:
        return 0

    current = load_glossary()
    added_count = 0
    source_filename = Path(source).name if ("/" in source or "\\" in source) else source
    if not source_filename:
        source_filename = "Document Corpus"

    for term, exp in extracted.items():
        if term not in current:
            current[term] = {
                "term": term,
                "expansion": exp,
                "source": source_filename,
                "sources": [source_filename],
                "user_id": user_id,
                "user_ids": [user_id]
            }
            added_count += 1
        else:
            entry = current[term]
            entry["expansion"] = exp  # Keep newest expansion
            entry["source"] = source_filename
            sources_list = entry.get("sources", [])
            if source_filename not in sources_list:
                sources_list.append(source_filename)
            entry["sources"] = sources_list
            user_ids_list = entry.get("user_ids", [])
            if user_id not in user_ids_list:
                user_ids_list.append(user_id)
            entry["user_ids"] = user_ids_list
            added_count += 1

    if added_count > 0:
        save_glossary(current)
        print(f"  [Glossary] Indexed {added_count} domain acronyms from '{source_filename}' (User: {user_id})")

    return added_count


def remove_source_from_glossary(source: str, user_id: Optional[str] = None) -> int:
    """
    Removes glossary definitions associated with a specific deleted source.
    If the term is not referenced by any other source, removes it completely.
    """
    if not source:
        return 0

    current = load_glossary()
    if not current:
        return 0

    target_name = Path(source).name.lower()
    target_raw = source.rstrip("/").lower()
    modified = False
    terms_to_delete = []

    for term, entry in current.items():
        entry_user = entry.get("user_id")
        entry_users = entry.get("user_ids", [entry_user] if entry_user else [])
        if user_id and user_id not in ("default", None) and user_id not in entry_users:
            continue

        sources = entry.get("sources", [entry.get("source")] if entry.get("source") else [])
        remaining_sources = [
            s for s in sources 
            if s and Path(s).name.lower() != target_name and s.rstrip("/").lower() != target_raw
        ]

        if not remaining_sources:
            terms_to_delete.append(term)
            modified = True
        elif len(remaining_sources) != len(sources):
            entry["sources"] = remaining_sources
            entry["source"] = remaining_sources[0]
            modified = True

    for term in terms_to_delete:
        del current[term]

    if modified:
        save_glossary(current)
        print(f"  [Glossary] Removed source '{source}' (Purged {len(terms_to_delete)} orphaned terms).")

    return len(terms_to_delete)


def clear_glossary(user_id: Optional[str] = None) -> None:
    """Clears glossary entries for a specific user, or all if user_id is None."""
    if user_id is None:
        save_glossary({})
        print("  [Glossary] Cleared all domain acronyms from disk.")
        return

    current = load_glossary()
    if not current:
        return

    new_glossary = {}
    for term, entry in current.items():
        entry_users = entry.get("user_ids", [entry.get("user_id")])
        remaining_users = [u for u in entry_users if u != user_id]
        if remaining_users:
            entry["user_ids"] = remaining_users
            new_glossary[term] = entry

    save_glossary(new_glossary)
    print(f"  [Glossary] Cleared domain acronyms for user '{user_id}'.")


def sync_glossary_with_active_sources(active_sources: set[str], user_id: Optional[str] = None) -> int:
    """
    Prunes orphaned glossary entries whose source documents no longer exist in Chroma.
    """
    current = load_glossary()
    if not current:
        return 0

    norm_active = {Path(s).name.lower() for s in active_sources if s}
    norm_active_full = {s.rstrip("/").lower() for s in active_sources if s}

    modified = False
    terms_to_delete = []

    for term, entry in current.items():
        entry_user = entry.get("user_id")
        entry_users = entry.get("user_ids", [entry_user] if entry_user else [])
        if user_id and user_id not in ("default", None) and user_id not in entry_users:
            continue

        sources = entry.get("sources", [entry.get("source")] if entry.get("source") else [])
        valid_sources = [
            s for s in sources 
            if s and (Path(s).name.lower() in norm_active or s.rstrip("/").lower() in norm_active_full)
        ]

        if not valid_sources:
            terms_to_delete.append(term)
            modified = True
        elif len(valid_sources) != len(sources):
            entry["sources"] = valid_sources
            entry["source"] = valid_sources[0]
            modified = True

    for term in terms_to_delete:
        del current[term]

    if modified:
        save_glossary(current)
        print(f"  [Glossary] Synced with active sources: pruned {len(terms_to_delete)} orphaned terms.")

    return len(terms_to_delete)


def get_glossary_for_user(
    user_id: Optional[str] = None, 
    active_sources: Optional[set[str]] = None
) -> list[dict]:
    """
    Returns a list of glossary entries filtered by user and/or active document sources.
    """
    current = load_glossary()
    if not current:
        return []

    norm_active = {Path(s).name.lower() for s in active_sources if s} if active_sources is not None else None
    norm_active_full = {s.rstrip("/").lower() for s in active_sources if s} if active_sources is not None else None

    results = []
    for term, entry in current.items():
        # Check user isolation
        if user_id:
            entry_users = entry.get("user_ids", [entry.get("user_id")])
            if user_id not in ("default", None) and user_id not in entry_users and "default" not in entry_users:
                continue

        # Check source validity if active_sources is provided
        if norm_active is not None:
            sources = entry.get("sources", [entry.get("source")] if entry.get("source") else [])
            matches = [
                s for s in sources 
                if s and (Path(s).name.lower() in norm_active or s.rstrip("/").lower() in norm_active_full)
            ]
            if not matches:
                continue

        results.append({
            "term": entry.get("term", term),
            "expansion": entry.get("expansion", ""),
            "source": entry.get("source", "Document Corpus")
        })

    return results


def enrich_query_with_glossary(
    query: str, 
    active_sources: Optional[set[str]] = None,
    user_id: Optional[str] = None
) -> str:
    """Enriches a query by expanding known acronyms found in the active corpus glossary."""
    terms = get_glossary_for_user(user_id=user_id, active_sources=active_sources)
    if not terms:
        return query

    glossary_map = {item["term"].upper(): item["expansion"] for item in terms}
    words = re.findall(r"\b[A-Za-z0-9]{2,8}\b", query)
    expansions_added = []

    for w in words:
        upper_w = w.upper()
        if upper_w in glossary_map and upper_w not in expansions_added:
            exp = glossary_map[upper_w]
            if exp and exp.lower() not in query.lower():
                expansions_added.append(f"{upper_w} ({exp})")

    if expansions_added:
        return f"{query} [{' | '.join(expansions_added)}]"

    return query
