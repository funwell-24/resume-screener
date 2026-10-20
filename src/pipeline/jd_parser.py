"""
Job description parser.

Turns a raw JD string into a `JobRequirements` object containing:
    - required_skills   (canonical, extracted via the same taxonomy)
    - title_skills      (skills in the JD title / first line)
    - required_years    (numeric, or None)
    - required_education (canonical level, or None)
    - raw_text          (preserved for similarity scoring)

Design:
    - Reuses the SAME skill extractor used for resumes â†’ symmetric
      comparison. This is what makes keyword scoring meaningful.
    - The JD title is heuristically the first non-empty line â€” resumes
      and JDs both follow this convention.
    - No NLP model here beyond skills.py â€” everything else is regex.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.extraction.skills import extract_skills
from src.extraction.experience import required_years_from_jd
from src.extraction.education import _detect_level  # reuse the level detector

if TYPE_CHECKING:
    from src.models import JobDescription

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class JobRequirements:
    raw_text: str
    title: str = ""
    required_skills: set[str] = field(default_factory=set)
    title_skills: set[str] = field(default_factory=set)
    required_years: float | None = None
    required_education: str | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "required_skills": sorted(self.required_skills),
            "title_skills": sorted(self.title_skills),
            "required_years": self.required_years,
            "required_education": self.required_education,
            "raw_text_length": len(self.raw_text),
        }

    def to_job_description(self) -> "JobDescription":
        """Convert to the JSON-safe job record."""
        from src.models import JobDescription
        return JobDescription(
            raw_text=self.raw_text,
            title=self.title,
            required_skills=sorted(self.required_skills),
            title_skills=sorted(self.title_skills),
            required_years=self.required_years,
            required_education=self.required_education,
        )


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

# Non-empty, not-a-bullet line at the top â€” likely the title
_TITLE_LINE = re.compile(r"^[A-Za-z][A-Za-z0-9 .'/&+\-]{2,80}$")

# Meta-keys that indicate a "Company: X" style line, not a title
_META_KEYS = {
    "company", "location", "salary", "department",
    "reports to", "job type", "position", "role",
}


def _guess_title(text: str) -> str:
    """Return the first plausible title line from the JD."""
    for line in text.split("\n")[:10]:
        stripped = line.strip().strip("#*=")
        if not stripped or len(stripped) > 100:
            continue
        if not _TITLE_LINE.match(stripped):
            continue
        if ":" in stripped:
            key = stripped.split(":", 1)[0].lower().strip()
            if key in _META_KEYS:
                continue
        return stripped
    return ""


def _extract_title_skills(title: str) -> set[str]:
    """Skills mentioned in the job title itself (used for weighting boost)."""
    return extract_skills(title) if title else set()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_job_description(jd_text: str) -> JobRequirements:
    """
    Parse a raw JD into a JobRequirements object.

    Safe to call with empty input â€” returns a JobRequirements with
    all fields None/empty rather than raising.
    """
    if not jd_text or not jd_text.strip():
        return JobRequirements(raw_text="")

    text = jd_text.strip()

    title = _guess_title(text)
    title_skills = _extract_title_skills(title)
    required_skills = extract_skills(text)

    # The title's skills are inherently required, so fold them in
    required_skills = required_skills | title_skills

    required_years = required_years_from_jd(text)

    # Education level â€” detection returns lowercase labels
    edu_level, _ = _detect_level(text)
    required_education = edu_level if edu_level != "unknown" else None

    jr = JobRequirements(
        raw_text=text,
        title=title,
        required_skills=required_skills,
        title_skills=title_skills,
        required_years=required_years,
        required_education=required_education,
    )

    if not required_skills:
        logger.warning(
            "JD yielded no required skills â€” keyword scoring will be skipped. "
            "Consider adding missing terms to config/skills.json."
        )

    return jr


def parse_job_description_file(
    path: str | os.PathLike[str],
) -> JobRequirements:
    """Convenience wrapper: parse a JD from a .txt file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JD file not found: {p}")
    return parse_job_description(p.read_text(encoding="utf-8-sig"))