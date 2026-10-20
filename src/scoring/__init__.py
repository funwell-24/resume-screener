"""
Scoring layer: turn extracted data into a ranked, explainable score.

Public API:
    score_candidate(jd, resume_data, ...) -> ScoreBreakdown
        One-shot helper that runs every sub-scorer and aggregates.

    Individual scorers (import if you want fine control):
        compute_keyword_score
        compute_similarity_scores
        compute_semantic_scores
        compute_experience_score
        aggregate_scores
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import settings

from .keyword_score import KeywordScore, compute_keyword_score
from .similarity_score import SimilarityScore, compute_similarity_scores
from .semantic_score import (
    SemanticScore,
    compute_semantic_scores,
    is_available as semantic_available,
)
from .experience_score import ExperienceScore, compute_experience_score
from .aggregator import ScoreBreakdown, aggregate_scores

logger = logging.getLogger(__name__)


@dataclass
class _JobSignals:
    """Pre-computed JD-side signals, shared across all resumes."""
    jd_text: str
    required_skills: set[str]
    title_skills: set[str]
    required_years: float | None


def score_candidate(
    *,
    jd_text: str,
    resume_text: str,
    resume_skills: set[str],
    candidate_years: float,
    required_skills: set[str],
    required_years: float | None,
    title_skills: set[str] | None = None,
    weights: dict[str, float] | None = None,
) -> ScoreBreakdown:
    """
    Score ONE candidate fully.

    If scoring many resumes, use `score_batch` below — it batches
    similarity computation for speed (TF-IDF fit-once).
    """
    kw = compute_keyword_score(
        resume_skills=resume_skills,
        required_skills=required_skills,
        title_skills=title_skills or set(),
    )

    # Single-resume similarity returns None — this is intentional.
    sim_map = compute_similarity_scores(jd_text, {"__one__": resume_text})
    sim = sim_map["__one__"]

    exp = compute_experience_score(
        candidate_years=candidate_years,
        required_years=required_years,
    )

    return aggregate_scores(kw, sim, exp, weights=weights)


def score_batch(
    *,
    jd_text: str,
    resumes: dict[str, dict],
    required_skills: set[str],
    required_years: float | None,
    title_skills: set[str] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, ScoreBreakdown]:
    """
    Score a BATCH of candidates efficiently.

    Parameters
    ----------
    resumes : dict[str, dict]
        {candidate_id: {"text": str, "skills": set[str], "years": float}}
        Normally the output of `pipeline.batch_runner`.

    Returns
    -------
    dict[str, ScoreBreakdown]
    """
    if not resumes:
        return {}

    # --- Similarity: batch (fit TF-IDF once) ---------------------------
    if settings.SIMILARITY_METHOD == "semantic":
        try:
            sem_map = compute_semantic_scores(
                jd_text, {k: v["text"] for k, v in resumes.items()}
            )
            sim_map = {
                k: SimilarityScore(score=sem_map[k].score, top_shared_terms=[])
                for k in resumes
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Semantic failed, falling back to TF-IDF: %s", exc)
            sim_map = compute_similarity_scores(
                jd_text, {k: v["text"] for k, v in resumes.items()}
            )
    else:
        sim_map = compute_similarity_scores(
            jd_text, {k: v["text"] for k, v in resumes.items()}
        )

    # --- Keyword + experience: per candidate --------------------------
    out: dict[str, ScoreBreakdown] = {}
    for key, r in resumes.items():
        kw = compute_keyword_score(
            resume_skills=r.get("skills", set()),
            required_skills=required_skills,
            title_skills=title_skills or set(),
        )
        exp = compute_experience_score(
            candidate_years=r.get("years", 0.0),
            required_years=required_years,
        )
        out[key] = aggregate_scores(kw, sim_map[key], exp, weights=weights)

    return out


__all__ = [
    "ScoreBreakdown",
    "KeywordScore",
    "SimilarityScore",
    "SemanticScore",
    "ExperienceScore",
    "compute_keyword_score",
    "compute_similarity_scores",
    "compute_semantic_scores",
    "compute_experience_score",
    "aggregate_scores",
    "score_candidate",
    "score_batch",
    "semantic_available",
]