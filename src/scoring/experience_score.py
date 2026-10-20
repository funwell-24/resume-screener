"""
Experience score: candidate years vs. JD's required years.

Formula:
    if required_years is None:
        score = None  (aggregator redistributes weight)
    else:
        ratio = candidate_years / required_years
        score = min(ratio, OVER_QUALIFIED_CAP)   (clipped to [0, 1])

Edge cases:
    - required_years == 0 → score = 1.0 (anyone qualifies)
    - candidate_years == 0 → score = 0.0
    - candidate "over-qualified" (10y vs 5y required) → capped at 1.0,
      unless EXPERIENCE_OVER_QUALIFIED_CAP > 1.0 to reward seniority
"""

from __future__ import annotations

from dataclasses import dataclass

from config import settings


@dataclass
class ExperienceScore:
    score: float | None          # None = no requirement stated
    candidate_years: float
    required_years: float | None
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "candidate_years": self.candidate_years,
            "required_years": self.required_years,
            "rationale": self.rationale,
        }


def compute_experience_score(
    candidate_years: float,
    required_years: float | None,
    over_qualified_cap: float | None = None,
) -> ExperienceScore:
    """Score candidate experience against JD requirement."""
    if over_qualified_cap is None:
        over_qualified_cap = settings.EXPERIENCE_OVER_QUALIFIED_CAP

    # JD silent → no score
    if required_years is None:
        return ExperienceScore(
            score=None,
            candidate_years=candidate_years,
            required_years=None,
            rationale="JD does not state a years requirement",
        )

    # Degenerate — JD says "0+ years"
    if required_years <= 0:
        return ExperienceScore(
            score=1.0,
            candidate_years=candidate_years,
            required_years=required_years,
            rationale="No specific years requirement",
        )

    ratio = candidate_years / required_years
    score = max(0.0, min(ratio, over_qualified_cap))

    if candidate_years <= 0:
        rationale = f"No experience detected (required {required_years:.1f}y)"
    elif ratio < 1.0:
        rationale = (
            f"{candidate_years:.1f}y vs required {required_years:.1f}y "
            f"({ratio * 100:.0f}% of requirement)"
        )
    else:
        rationale = (
            f"{candidate_years:.1f}y meets required {required_years:.1f}y "
            f"({ratio * 100:.0f}% of requirement)"
        )

    return ExperienceScore(
        score=score,
        candidate_years=candidate_years,
        required_years=required_years,
        rationale=rationale,
    )