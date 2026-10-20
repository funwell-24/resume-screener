"""
Candidate — the serializable, display-ready record for one applicant.

This is the SHAPE that flows through the UI, exports, and tests.
It is intentionally separate from `ProcessedResume` (pipeline layer),
which carries heavy internal objects (raw text, ResumeSections,
spaCy-adjacent structures) not suitable for serialization or display.

Conversion:
    ProcessedResume  ──.to_candidate()──►  Candidate
    Candidate        ──.to_dict()─────►  dict  (JSON-safe)

Design principles:
    - All fields are JSON-serializable primitives or lists of them.
    - Immutable-by-convention (not frozen — dict field needs mutation),
      but treat as read-only once constructed.
    - No business logic here. Pure data.
    - `from_dict` allows round-tripping through storage (cache, tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# Valid education levels — mirrors education.py DegreeLevel
_EDUCATION_LEVELS = {
    "unknown", "other", "high_school", "certificate",
    "associate", "bachelor", "master", "mba", "doctorate",
}


@dataclass
class Candidate:
    """A single applicant, ready to display / export / test."""

    # ---- Identity ---------------------------------------------------
    filename: str                               # e.g. "alice_cv.pdf"
    file_path: str = ""                         # absolute or relative path
    name: str = ""                              # extracted display name

    # ---- Contact ----------------------------------------------------
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""

    # ---- Skills -----------------------------------------------------
    skills: list[str] = field(default_factory=list)             # canonical, sorted
    matched_skills: list[str] = field(default_factory=list)     # vs. this JD
    missing_skills: list[str] = field(default_factory=list)     # vs. this JD

    # ---- Experience -------------------------------------------------
    total_years: float = 0.0
    n_jobs: int = 0

    # ---- Education --------------------------------------------------
    education_level: str = "unknown"            # must be in _EDUCATION_LEVELS
    education_institution: str = ""
    education_field: str = ""

    # ---- Score ------------------------------------------------------
    score: float | None = None                  # 0..1
    display_score: float | None = None          # 0..100 (rounded)
    rank: int | None = None
    recommended_for_review: bool = False

    # ---- Diagnostics ------------------------------------------------
    num_pages: int = 0
    used_ocr: bool = False
    error: str | None = None

    # ---- Passthrough for extra data (score breakdown, etc.) ---------
    extras: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        # Normalize skills: sorted, unique
        self.skills = sorted(set(self.skills))
        self.matched_skills = sorted(set(self.matched_skills))
        self.missing_skills = sorted(set(self.missing_skills))

        # Clamp score
        if self.score is not None:
            self.score = max(0.0, min(1.0, float(self.score)))
        if self.display_score is not None:
            self.display_score = round(float(self.display_score), 1)

        # Clamp years
        self.total_years = max(0.0, float(self.total_years or 0.0))

        # Validate education level
        if self.education_level not in _EDUCATION_LEVELS:
            self.education_level = "unknown"

        # Derive display_score from score if not provided
        if self.display_score is None and self.score is not None:
            self.display_score = round(self.score * 100, 1)

        # Derive recommendation flag if not provided but score is
        if (
            not self.recommended_for_review
            and self.score is not None
            and self.score >= 0.60
        ):
            self.recommended_for_review = True

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------
    @property
    def display_name(self) -> str:
        """Name if extracted, else filename stem."""
        if self.name:
            return self.name
        from pathlib import Path
        return Path(self.filename).stem

    @property
    def n_skills(self) -> int:
        return len(self.skills)

    @property
    def has_score(self) -> bool:
        return self.score is not None

    @property
    def match_coverage(self) -> float:
        """Fraction of required skills matched, or 0 if no requirement."""
        total = len(self.matched_skills) + len(self.missing_skills)
        if total == 0:
            return 0.0
        return len(self.matched_skills) / total

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candidate":
        """Inverse of to_dict. Ignores unknown keys, defaults missing ones."""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Presentation helpers
    # ------------------------------------------------------------------
    def summary_row(self) -> dict[str, Any]:
        """Compact row for UI tables / CSV exports."""
        return {
            "Rank": self.rank,
            "Candidate": self.display_name,
            "Score": self.display_score,
            "Matched": len(self.matched_skills),
            "Missing": len(self.missing_skills),
            "Years": round(self.total_years, 1),
            "Education": self.education_level,
            "Review": "✓" if self.recommended_for_review else "",
            "File": self.filename,
        }