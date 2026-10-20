"""
Aggregate sub-scores into a final score + explanation.

Rules:
    1. Every sub-score is [0, 1] or None.
    2. If a sub-score is None (signal absent), its weight is redistributed
       proportionally among the remaining weights (unless the caller sets
       REDISTRIBUTE_MISSING_EXPERIENCE = False for the experience signal).
    3. If ALL sub-scores are None → final score is None.
    4. If all weights for remaining signals are 0 → final score is None.

This function is PURE. No I/O, no LLM, no side effects. That's what
makes it testable and trustworthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import settings
from .keyword_score import KeywordScore
from .similarity_score import SimilarityScore
from .experience_score import ExperienceScore


@dataclass
class ScoreBreakdown:
    """Full record of how a candidate's score was assembled."""

    final: float | None                       # 0..1, or None if no signal
    keyword: KeywordScore
    similarity: SimilarityScore
    experience: ExperienceScore
    weights_used: dict[str, float] = field(default_factory=dict)
    contributions: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    # ---- Presentation helpers ----------------------------------------
    @property
    def display_score(self) -> float | None:
        if self.final is None:
            return None
        return round(
            self.final * settings.DISPLAY_SCORE_SCALE,
            settings.DISPLAY_SCORE_DECIMALS,
        )

    @property
    def matched_skills(self) -> list[str]:
        return sorted(self.keyword.matched)

    @property
    def missing_skills(self) -> list[str]:
        return sorted(self.keyword.missing)

    @property
    def recommended_for_review(self) -> bool:
        return (
            self.final is not None
            and self.final >= settings.REVIEW_BADGE_THRESHOLD
        )

    def to_dict(self) -> dict:
        return {
            "final": self.final,
            "display_score": self.display_score,
            "recommended_for_review": self.recommended_for_review,
            "weights_used": self.weights_used,
            "contributions": self.contributions,
            "notes": self.notes,
            "keyword": self.keyword.to_dict(),
            "similarity": self.similarity.to_dict(),
            "experience": self.experience.to_dict(),
        }

    def explain(self) -> str:
        """Human-readable one-paragraph explanation."""
        if self.final is None:
            return "No usable signal — cannot compute a score."
        parts = [
            f"Final: {self.display_score}/100",
            f"Skills matched: {len(self.keyword.matched)}/{len(self.keyword.required)}",
            self.experience.rationale,
        ]
        if self.notes:
            parts.append("Notes: " + "; ".join(self.notes))
        return " · ".join(p for p in parts if p)


def _effective_weights(
    components: dict[str, float | None],
    base_weights: dict[str, float],
) -> dict[str, float]:
    """
    Redistribute weights so available signals sum to 1.0.

    Weight for missing (None) signals is spread proportionally over the
    signals that DO have a value. If no signal has a value, returns {}.
    """
    active = {k: w for k, w in base_weights.items() if components.get(k) is not None}
    total_active = sum(active.values())
    if total_active <= 0:
        return {}
    return {k: w / total_active for k, w in active.items()}


def aggregate_scores(
    keyword: KeywordScore,
    similarity: SimilarityScore,
    experience: ExperienceScore,
    weights: dict[str, float] | None = None,
) -> ScoreBreakdown:
    """Combine sub-scores into a final score with full traceability."""
    base = dict(weights or settings.SCORE_WEIGHTS)

    if abs(sum(base.values()) - 1.0) > 1e-6:
        raise ValueError(
            f"Score weights must sum to 1.0, got {sum(base.values()):.4f}: {base}"
        )

    components = {
        "keyword": keyword.score,
        "similarity": similarity.score,
        "experience": experience.score,
    }

    # Special case: don't redistribute experience weight if the JD is silent
    # and the caller wants to keep experience's weight as a small penalty.
    if (
        not settings.REDISTRIBUTE_MISSING_EXPERIENCE
        and components["experience"] is None
    ):
        # Recompute without the "redistribution" for experience
        base_without_exp = {k: v for k, v in base.items() if k != "experience"}
        base_without_exp["experience"] = 0.0
        components_noexp = dict(components)
        components_noexp.pop("experience")
        eff = _effective_weights(components_noexp, base_without_exp)
        eff["experience"] = base["experience"]
    else:
        eff = _effective_weights(components, base)

    if not eff:
        return ScoreBreakdown(
            final=None,
            keyword=keyword,
            similarity=similarity,
            experience=experience,
            weights_used={},
            contributions={},
            notes=["No scoring signal available"],
        )

    final = 0.0
    contributions: dict[str, float] = {}
    for name, weight in eff.items():
        value = components.get(name)
        if value is None:
            continue
        contribution = weight * value
        contributions[name] = round(contribution, 6)
        final += contribution

    final = max(0.0, min(1.0, final))

    notes: list[str] = []
    if keyword.score is None:
        notes.append("No required skills in JD — keyword signal skipped")
    if similarity.score is None:
        notes.append("Similarity signal unavailable")
    if experience.score is None:
        notes.append(experience.rationale)

    return ScoreBreakdown(
        final=final,
        keyword=keyword,
        similarity=similarity,
        experience=experience,
        weights_used={k: round(v, 4) for k, v in eff.items()},
        contributions=contributions,
        notes=notes,
    )