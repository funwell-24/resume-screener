"""
Score view models.

The CANONICAL ScoreBreakdown lives in src/scoring/aggregator.py — it is
re-exported here so consumers can `from src.models import ScoreBreakdown`
without reaching into scoring/ directly. This keeps the models package
as the single import surface for typed data.

Additionally defines `ScoreView` — a flattened, JSON-safe projection of
a ScoreBreakdown for UI display and CSV export. Converting between them
is a pure function with no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Re-export the canonical ScoreBreakdown
from src.scoring.aggregator import ScoreBreakdown  # noqa: F401


@dataclass
class ScoreView:
    """
    Flattened, serializable view of a ScoreBreakdown.

    Why a separate class:
        - ScoreBreakdown holds nested dataclasses (KeywordScore, etc.)
          that carry sets — not JSON-safe.
        - The UI wants a flat dict.
        - Exports (CSV/JSON) want stable column names.
    """

    final: float | None = None
    display_score: float | None = None
    recommended_for_review: bool = False

    # Sub-scores (None = signal absent)
    keyword_score: float | None = None
    similarity_score: float | None = None
    experience_score: float | None = None

    # Components
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)

    candidate_years: float = 0.0
    required_years: float | None = None

    top_shared_terms: list[tuple[str, float]] = field(default_factory=list)

    # Explanation
    weights_used: dict[str, float] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    explanation: str = ""

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert (term, weight) tuples → JSON-safe dicts
        d["top_shared_terms"] = [
            {"term": t, "weight": w} for t, w in self.top_shared_terms
        ]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScoreView":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}

        # Restore tuples
        if "top_shared_terms" in filtered:
            filtered["top_shared_terms"] = [
                (item["term"], item["weight"])
                if isinstance(item, dict) else tuple(item)
                for item in filtered["top_shared_terms"]
            ]
        return cls(**filtered)


def to_score_view(sb: ScoreBreakdown) -> ScoreView:
    """
    Pure conversion: ScoreBreakdown → ScoreView.

    Idempotent, side-effect free, safe to call in loops.
    """
    return ScoreView(
        final=sb.final,
        display_score=sb.display_score,
        recommended_for_review=sb.recommended_for_review,
        keyword_score=sb.keyword.score,
        similarity_score=sb.similarity.score,
        experience_score=sb.experience.score,
        matched_skills=list(sb.matched_skills),
        missing_skills=list(sb.missing_skills),
        required_skills=sorted(sb.keyword.required),
        candidate_years=float(sb.experience.candidate_years or 0.0),
        required_years=sb.experience.required_years,
        top_shared_terms=list(sb.similarity.top_shared_terms),
        weights_used=dict(sb.weights_used),
        contributions=dict(sb.contributions),
        notes=list(sb.notes),
        explanation=sb.explain(),
    )