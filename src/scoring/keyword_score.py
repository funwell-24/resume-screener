"""
Keyword score: skill overlap between resume and job description.

Formula:
    base = |matched| / |required|
    score = weighted version if TITLE_SKILL_BOOST != 1.0, else base

Design:
    - Symmetric — no length penalty for either side (JD and resume
      both go through the SAME skill extractor, so ambiguity is fair)
    - If JD has zero required skills, return None (signal "no signal")
      rather than 0.0 — the aggregator redistributes its weight.
    - Explainable — always returns matched and missing skill sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import settings


@dataclass
class KeywordScore:
    score: float | None          # None = not applicable (no required skills)
    matched: set[str] = field(default_factory=set)
    missing: set[str] = field(default_factory=set)
    required: set[str] = field(default_factory=set)
    title_boosted: set[str] = field(default_factory=set)

    @property
    def coverage(self) -> float:
        """Raw overlap fraction regardless of weight/boost."""
        if not self.required:
            return 0.0
        return len(self.matched) / len(self.required)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "coverage": self.coverage,
            "matched": sorted(self.matched),
            "missing": sorted(self.missing),
            "required": sorted(self.required),
            "title_boosted": sorted(self.title_boosted),
        }


def compute_keyword_score(
    resume_skills: set[str],
    required_skills: set[str],
    title_skills: set[str] | None = None,
    title_boost: float | None = None,
    zero_if_no_match: bool | None = None,
) -> KeywordScore:
    """
    Compute the keyword score.

    Parameters
    ----------
    resume_skills : set[str]
        Canonical skills extracted from the resume.
    required_skills : set[str]
        Canonical skills required by the JD.
    title_skills : set[str] | None
        Skills mentioned in the JD's title/summary — get a boost.
    title_boost : float | None
        Multiplier for title-skill weight. Defaults to settings.
    zero_if_no_match : bool | None
        If True (default from settings), force 0.0 when no skills match.
    """
    if title_boost is None:
        title_boost = settings.TITLE_SKILL_BOOST
    if zero_if_no_match is None:
        zero_if_no_match = settings.KEYWORD_ZERO_IF_NO_MATCH
    if title_skills is None:
        title_skills = set()

    required = {s.strip().lower() for s in required_skills if s and s.strip()}
    if not required:
        return KeywordScore(score=None)

    resume_norm = {s.strip().lower() for s in resume_skills if s and s.strip()}

    matched = resume_norm & required
    missing = required - resume_norm
    title_set = {s.strip().lower() for s in title_skills} & required

    # If nothing matched → 0.0 (or None → covered below)
    if zero_if_no_match and not matched:
        return KeywordScore(
            score=0.0,
            matched=matched,
            missing=missing,
            required=required,
            title_boosted=title_set,
        )

    # Weighted: title skills count 1.0 * title_boost, others 1.0
    if title_boost == 1.0:
        score = len(matched) / len(required)
    else:
        total_weight = len(required) - len(title_set) + len(title_set) * title_boost
        matched_weight = (
            len(matched - title_set)
            + len(matched & title_set) * title_boost
        )
        score = matched_weight / total_weight if total_weight > 0 else 0.0

    score = max(0.0, min(1.0, score))

    return KeywordScore(
        score=score,
        matched=matched,
        missing=missing,
        required=required,
        title_boosted=title_set,
    )