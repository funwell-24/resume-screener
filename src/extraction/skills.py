"""
Skill extraction using a curated taxonomy and regex matching.

Design:
    - Load curated taxonomy from config/skills.json
    - Match case-insensitive, whole-phrase, word-boundary
    - Return canonical skills + optional evidence snippets
    - Version-independent: pure Python regex, no spaCy dependency

Why regex instead of spaCy's PhraseMatcher:
    - PhraseMatcher on Python 3.14 + spaCy 3.8 silently returns no
      matches even when patterns are correctly added (known issue
      with hash round-trip changes).
    - Regex is deterministic, debuggable, and works on every Python
      version.
    - For a ~200-skill taxonomy, regex is faster than PhraseMatcher.
    - Word boundaries via lookarounds correctly handle aliases like
      "c++", "c#", ".net", "node.js" (plain \\b fails on these).
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "skills.json"
)


# ---------------------------------------------------------------------------
# Taxonomy loading
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_taxonomy(
    path: str | Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, set[str]]:
    """
    Load skills.json → {canonical_skill: {alias1, alias2, ...}}.

    The canonical name itself is always included as an alias.
    Result is cached — safe to call from every resume.
    """
    path = Path(path)
    with path.open(encoding="utf-8-sig") as f:
        raw = json.load(f)

    taxonomy: dict[str, set[str]] = {}
    for _category, skills in raw.items():
        if not isinstance(skills, dict):
            continue
        for canonical, aliases in skills.items():
            key = canonical.strip().lower()
            taxonomy.setdefault(key, set()).add(key)
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias.strip():
                        taxonomy[key].add(alias.strip().lower())
    return taxonomy


# ---------------------------------------------------------------------------
# Pattern compilation
# ---------------------------------------------------------------------------

def _compile_pattern(alias: str) -> re.Pattern:
    """
    Compile an alias into a word-boundary regex.

    Lookarounds (instead of \\b) handle aliases ending in non-word
    chars: "c++", "c#", ".net", "node.js", "scikit-learn".
    """
    escaped = re.escape(alias)
    return re.compile(
        r"(?<![a-zA-Z0-9_])" + escaped + r"(?![a-zA-Z0-9_])",
        re.IGNORECASE,
    )


@lru_cache(maxsize=1)
def _build_pattern_index() -> tuple[tuple[str, re.Pattern], ...]:
    """
    Build a flat tuple of (canonical, compiled_pattern) — one entry per alias.

    Cached — the taxonomy rarely changes at runtime.
    """
    taxonomy = load_taxonomy()
    index: list[tuple[str, re.Pattern]] = []

    for canonical, aliases in taxonomy.items():
        for alias in aliases:
            if not alias:
                continue
            try:
                index.append((canonical, _compile_pattern(alias)))
            except re.error as exc:
                logger.warning(
                    "Bad alias %r for %r: %s", alias, canonical, exc
                )

    logger.debug(
        "Built skill pattern index: %d aliases across %d skills",
        len(index), len(taxonomy),
    )
    return tuple(index)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_skills(text: str) -> set[str]:
    """
    Return the set of canonical skills found in `text`.

    Case-insensitive, whole-phrase, word-boundary matches.
    """
    if not text or not text.strip():
        return set()

    index = _build_pattern_index()
    found: set[str] = set()

    for canonical, pattern in index:
        if pattern.search(text):
            found.add(canonical)

    return found


def extract_skills_with_evidence(text: str) -> dict[str, list[str]]:
    """
    Same as extract_skills, but also return surrounding text for each
    match. Used by the UI to explain "why did this match?".
    """
    if not text or not text.strip():
        return {}

    index = _build_pattern_index()
    evidence: dict[str, list[str]] = {}
    WINDOW = 60

    for canonical, pattern in index:
        for match in pattern.finditer(text):
            lo = max(0, match.start() - WINDOW)
            hi = min(len(text), match.end() + WINDOW)
            snippet = text[lo:hi].replace("\n", " ").strip()
            evidence.setdefault(canonical, []).append(snippet)
            break  # one snippet per (skill, alias) pair is enough

    return {k: list(dict.fromkeys(v)) for k, v in evidence.items()}


def skills_by_section(sections: dict[str, str]) -> dict[str, set[str]]:
    """Extract skills per resume section."""
    return {
        name: extract_skills(body)
        for name, body in sections.items()
        if body
    }


def extract_required_skills_from_jd(jd_text: str) -> set[str]:
    """Extract skills from a JD using the SAME taxonomy as resumes."""
    return extract_skills(jd_text)