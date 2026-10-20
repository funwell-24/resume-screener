"""
JobDescription — the parsed, serializable form of the JD.

Sibling of `JobRequirements` (pipeline layer). JobRequirements is what
jd_parser produces internally; JobDescription is the display-ready,
JSON-safe record. JobRequirements.to_job_description() converts one to
the other, and this dataclass is what the UI/export layer uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class JobDescription:
    """The parsed job description, ready to display / export / store."""

    # ---- Raw content ------------------------------------------------
    raw_text: str = ""

    # ---- Parsed fields ----------------------------------------------
    title: str = ""
    required_skills: list[str] = field(default_factory=list)
    title_skills: list[str] = field(default_factory=list)
    required_years: float | None = None
    required_education: str | None = None

    # ---- Optional metadata ------------------------------------------
    company: str = ""
    location: str = ""
    source: str = ""                            # filename or "pasted"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        self.required_skills = sorted(set(self.required_skills))
        self.title_skills = sorted(set(self.title_skills))

        if self.required_years is not None:
            yrs = float(self.required_years)
            if yrs < 0 or yrs > 40:
                # Implausible — treat as missing signal
                self.required_years = None
            else:
                self.required_years = yrs

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def has_required_skills(self) -> bool:
        return bool(self.required_skills)

    @property
    def has_years_requirement(self) -> bool:
        return self.required_years is not None

    @property
    def display_title(self) -> str:
        return self.title or "Untitled Position"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobDescription":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------
    def summary_lines(self) -> list[str]:
        """Human-readable one-line-per-field summary for the UI."""
        lines = [f"Title: {self.display_title}"]
        if self.company:
            lines.append(f"Company: {self.company}")
        if self.required_skills:
            lines.append(f"Required skills ({len(self.required_skills)}): "
                         + ", ".join(self.required_skills))
        if self.required_years is not None:
            lines.append(f"Minimum experience: {self.required_years:.1f} years")
        if self.required_education:
            lines.append(f"Education: {self.required_education}")
        return lines