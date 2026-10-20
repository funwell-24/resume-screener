"""
Split a resume's cleaned text into logical sections.

Why this matters:
    Without sectioning, "Python" in a hobbies line ("I enjoy Python
    programming as a hobby") gets counted as a professional skill.
    Sectioning lets each downstream extractor scope its search.

Approach:
    1. Scan for common section header keywords (case-insensitive).
    2. A line counts as a header if it's short (< 40 chars), contains
       a known keyword, and doesn't end with a period.
    3. Split text on header lines. Unrecognized prefix → "header" section.

This is heuristic, not perfect. Real resumes have wild layouts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Canonical section names we recognize. Aliases point to canonical.
_SECTION_ALIASES: dict[str, list[str]] = {
    "summary": [
        "summary", "professional summary", "profile", "about",
        "objective", "career objective", "overview",
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment history", "work history", "career history",
        "relevant experience", "employment",
    ],
    "education": [
        "education", "academic background", "academic history",
        "educational background", "qualifications", "academic qualifications",
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "competencies",
        "technical proficiencies", "proficiencies", "expertise",
        "technologies", "tools", "tech stack",
    ],
    "projects": [
        "projects", "personal projects", "side projects",
        "selected projects", "key projects",
    ],
    "certifications": [
        "certifications", "certificates", "licenses",
        "certifications & licenses", "professional certifications",
    ],
    "awards": ["awards", "honors", "achievements", "accomplishments"],
    "publications": ["publications", "papers", "research"],
    "languages": ["languages", "language proficiency"],
    "interests": ["interests", "hobbies", "activities", "personal interests"],
    "volunteer": ["volunteer", "volunteering", "community involvement"],
    "references": ["references"],
}

# Invert: alias → canonical
_ALIAS_TO_CANON: dict[str, str] = {
    alias: canon
    for canon, aliases in _SECTION_ALIASES.items()
    for alias in aliases
}

# Precompiled pattern: a short line that is essentially just a header.
# Matches "EXPERIENCE", "Work Experience:", "TECHNICAL SKILLS", etc.
_HEADER_LINE = re.compile(
    r"^\s*([A-Za-z][A-Za-z\s&/,\-]{1,38}?)\s*:?\s*$"
)

_HEADER_MAX_LEN = 40


@dataclass
class ResumeSections:
    """Result of splitting a resume into sections."""
    header: str = ""
    summary: str = ""
    experience: str = ""
    education: str = ""
    skills: str = ""
    projects: str = ""
    certifications: str = ""
    awards: str = ""
    publications: str = ""
    languages: str = ""
    interests: str = ""
    volunteer: str = ""
    references: str = ""
    other: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, str]:
        """Return all non-empty sections as {name: text}."""
        out: dict[str, str] = {}
        for k, v in self.__dict__.items():
            if k == "other":
                out.update(v)
            elif v:
                out[k] = v
        return out

    def get(self, name: str) -> str:
        """Case-insensitive section access. Returns '' if unknown."""
        return self.as_dict().get(name.lower(), "")

    def all_text(self) -> str:
        """Concatenate every section back into one string."""
        return "\n\n".join(self.as_dict().values())


def _classify_header(line: str) -> str | None:
    """
    Return the canonical section name if this line looks like a header,
    else None.
    """
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > _HEADER_MAX_LEN:
        return None
    if stripped.endswith("."):
        return None  # sentences, not headers

    lowered = stripped.lower()

    # Exact match on known aliases
    if lowered in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[lowered]

    # Try squashed form (e.g., "TECHNICAL SKILLS" → "technical skills")
    squashed = re.sub(r"\s+", " ", lowered)
    if squashed in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[squashed]

    # Sometimes headers have extra decoration: "== EXPERIENCE ==",
    # "** Skills **", "--- EDUCATION ---"
    cleaned = re.sub(r"[^\w\s&/,\-]", "", stripped).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[cleaned]

    return None


def split_sections(text: str) -> ResumeSections:
    """
    Split cleaned resume text into sections by detecting header lines.

    Unrecognized headers accumulate into `other` under the header's raw name.
    Text before the first recognized header goes into `header`
    (usually the name/contact block).
    """
    sections = ResumeSections()
    if not text or not text.strip():
        return sections

    lines = text.split("\n")

    current_name: str = "header"
    buffer: list[str] = []
    other_names: list[str] = []  # preserves order for `other` dict

    def flush():
        nonlocal buffer, current_name
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        if not body:
            buffer = []
            return
        if current_name in ResumeSections.__dataclass_fields__:
            existing = getattr(sections, current_name, "")
            setattr(sections, current_name, (existing + "\n" + body).strip() if existing else body)
        else:
            existing = sections.other.get(current_name, "")
            sections.other[current_name] = (existing + "\n" + body).strip() if existing else body
            if current_name not in other_names:
                other_names.append(current_name)
        buffer = []

    for line in lines:
        canon = _classify_header(line)
        if canon is not None:
            flush()
            current_name = canon
        else:
            # Non-header line might still be a *custom* header (e.g., "AWARDS 2020")
            # — skip. Keep it simple: treat as content.
            buffer.append(line)

    flush()
    return sections


def get_section(text: str, name: str) -> str:
    """Convenience: return the text of one section. '' if not found."""
    return split_sections(text).get(name)