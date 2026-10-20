"""
Education extraction.

Approach:
    - Degree level: regex over a controlled vocabulary of degree keywords
      (BSc, MSc, PhD, MBA, Bachelor, Master, Doctorate, etc.)
    - Institution: spaCy NER for ORG + regex fallback for "University",
      "College", "Institute" keywords
    - Graduation year: nearby 4-digit year (1990–2030)

Why not pure NER:
    spaCy's ORG entity sometimes grabs "MIT Media Lab" correctly but
    misses "Stanford" or catches companies ("Google"). Combining NER +
    keyword regex gives us robust coverage on resumes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import spacy


DegreeLevel = Literal[
    "high_school", "associate", "bachelor", "master", "doctorate",
    "mba", "certificate", "other", "unknown"
]


# Canonical level from keyword. Longer/rarer terms first so "phd" beats "d".
_DEGREE_KEYWORDS: list[tuple[str, DegreeLevel]] = [
    (r"ph\.?\s*d\.?\b", "doctorate"),
    (r"doctorate", "doctorate"),
    (r"d\.?phil\b", "doctorate"),
    (r"m\.?b\.?a\.?\b", "mba"),
    (r"master'?s?\b", "master"),
    (r"m\.?sc\.?\b", "master"),
    (r"m\.?s\.?(?:\s|$)", "master"),
    (r"m\.?eng\.?\b", "master"),
    (r"ma\b", "master"),
    (r"bachelor'?s?\b", "bachelor"),
    (r"b\.?sc\.?\b", "bachelor"),
    (r"b\.?s\.?(?:\s|$)", "bachelor"),
    (r"b\.?eng\.?\b", "bachelor"),
    (r"b\.?a\.?(?:\s|$)", "bachelor"),
    (r"undergraduate", "bachelor"),
    (r"associate'?s?\b", "associate"),
    (r"a\.?a\.?(?:\s|$)", "associate"),
    (r"a\.?s\.?(?:\s|$)", "associate"),
    (r"high\s+school", "high_school"),
    (r"ged\b", "high_school"),
    (r"certificate", "certificate"),
]

_DEGREE_PATTERNS = [
    (re.compile(kw, re.IGNORECASE), level)
    for kw, level in _DEGREE_KEYWORDS
]

_INSTITUTION_KEYWORD = re.compile(
    r"\b([A-Z][\w&'.\-]*(?:\s+[A-Z][\w&'.\-]*){0,4}\s+"
    r"(?:University|College|Institute|School|Academy|Polytechnic))\b"
)

_YEAR = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")

# Field of study hints (very loose)
_FIELD_HINTS = [
    "computer science", "software engineering", "information technology",
    "data science", "mathematics", "statistics", "physics", "chemistry",
    "biology", "economics", "business administration", "electrical engineering",
    "mechanical engineering", "civil engineering", "psychology",
    "information systems", "artificial intelligence", "machine learning",
]


@dataclass
class EducationEntry:
    degree_level: DegreeLevel = "unknown"
    degree_text: str = ""
    institution: str = ""
    year: int | None = None
    field: str = ""


@dataclass
class EducationInfo:
    highest_level: DegreeLevel = "unknown"
    entries: list[EducationEntry] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)

    def level_rank(self) -> int:
        """Numeric rank for comparing candidate vs. job requirement."""
        rank = {
            "unknown": 0, "other": 0, "high_school": 1,
            "certificate": 2, "associate": 2, "bachelor": 3,
            "master": 4, "mba": 4, "doctorate": 5,
        }
        return rank.get(self.highest_level, 0)


@lru_cache(maxsize=1)
def _nlp():
    try:
        return spacy.load("en_core_web_sm", disable=["lemmatizer"])
    except OSError as exc:
        raise RuntimeError(
            "spaCy model 'en_core_web_sm' not found. "
            "Install with: python -m spacy download en_core_web_sm"
        ) from exc


def _detect_level(text: str) -> tuple[DegreeLevel, str]:
    """Return (level, matched text) for the highest degree mentioned."""
    best: DegreeLevel = "unknown"
    best_text = ""
    rank = {
        "unknown": 0, "other": 1, "high_school": 2, "certificate": 3,
        "associate": 3, "bachelor": 4, "master": 5, "mba": 5, "doctorate": 6,
    }
    for pattern, level in _DEGREE_PATTERNS:
        for match in pattern.finditer(text):
            if rank[level] > rank[best]:
                best = level
                # Expand context around the match to capture full degree text
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                best_text = text[start:end].replace("\n", " ").strip()
    return best, best_text


def _find_institutions(text: str) -> list[str]:
    """Return deduplicated institution names in order of first appearance."""
    found: list[str] = []

    # NER pass
    doc = _nlp()(text)
    for ent in doc.ents:
        if ent.label_ == "ORG" and any(
            kw in ent.text for kw in ("University", "College", "Institute", "School")
        ):
            found.append(ent.text.strip())

    # Regex pass (catches things NER misses)
    for match in _INSTITUTION_KEYWORD.finditer(text):
        found.append(match.group(1).strip())

    # Dedupe, preserve order
    return list(dict.fromkeys(found))


def _nearest_year(text: str, position: int, window: int = 200) -> int | None:
    """Return the closest 4-digit year to a position in the text."""
    lo = max(0, position - window)
    hi = min(len(text), position + window)
    window_text = text[lo:hi]

    best_year: int | None = None
    best_dist = 10**9
    for match in _YEAR.finditer(window_text):
        year = int(match.group())
        if not (1990 <= year <= 2030):
            continue
        # absolute distance from position in the original text
        center = lo + match.start()
        dist = abs(center - position)
        if dist < best_dist:
            best_dist = dist
            best_year = year
    return best_year


def _find_fields(text: str) -> list[str]:
    lowered = text.lower()
    return [f for f in _FIELD_HINTS if f in lowered]


def extract_education(text: str) -> EducationInfo:
    """
    Extract education info from cleaned resume text.
    Should be called on the education section (from sections.py)
    for best results, but works on full text too.
    """
    info = EducationInfo()
    if not text or not text.strip():
        return info

    level, degree_text = _detect_level(text)
    institutions = _find_institutions(text)
    fields = _find_fields(text)

    # Find year near each institution mention (or first year overall)
    year: int | None = None
    if institutions:
        first_inst_pos = text.find(institutions[0])
        if first_inst_pos >= 0:
            year = _nearest_year(text, first_inst_pos)
    if year is None:
        m = _YEAR.search(text)
        if m:
            y = int(m.group())
            if 1990 <= y <= 2030:
                year = y

    entry = EducationEntry(
        degree_level=level,
        degree_text=degree_text,
        institution=institutions[0] if institutions else "",
        year=year,
        field=fields[0] if fields else "",
    )
    if any([entry.degree_text, entry.institution, entry.year]):
        info.entries.append(entry)

    info.highest_level = level
    info.fields = fields
    return info