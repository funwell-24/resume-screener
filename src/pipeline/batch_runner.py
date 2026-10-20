"""
Batch processing: many PDFs → extraction → scoring → ranked list.

Public API:
    run_batch(pdf_paths, job, ...) -> BatchResult

Design:
    - Extraction phase first (sequential — cheap, and PDF parsing is
      largely I/O bound; adding threads here is a future optimization).
    - Scoring phase second (batched — TF-IDF fit once across all resumes).
    - Failures NEVER kill the batch. Failed PDFs become entries in
      `BatchResult.failures` and are excluded from ranking.
    - Returns a fully sortable, serializable structure built on the
      models layer (Candidate + ScoreView). The UI does not compute
      anything — it only displays what this module produces.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from config import settings
from src.scoring import score_batch
from src.models import Candidate, ScoreView, to_score_view
from .jd_parser import JobRequirements, parse_job_description
from .resume_pipeline import ProcessedResume, process_resume

if TYPE_CHECKING:
    pass  # reserved for future type-only imports

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class RankedCandidate:
    """
    A single ranked candidate, backed by the models layer.

    `candidate` carries the JSON-safe display record (contact, skills,
    education, etc.). `score` carries the flattened score breakdown.
    `candidate.matched_skills` / `.missing_skills` / `.score` /
    `.rank` / `.recommended_for_review` are populated here so the
    Candidate is fully self-describing.
    """

    rank: int
    candidate: Candidate
    score: ScoreView

    @property
    def display_score(self) -> float | None:
        return self.candidate.display_score

    def to_dict(self) -> dict:
        d = self.candidate.to_dict()
        d["rank"] = self.rank
        d["score_detail"] = self.score.to_dict()
        return d


@dataclass
class BatchResult:
    """Full result of running a batch."""

    job: JobRequirements
    ranked: list[RankedCandidate] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    total_input: int = 0

    @property
    def n_processed(self) -> int:
        return len(self.ranked)

    @property
    def n_failed(self) -> int:
        return len(self.failures)

    def to_dict(self) -> dict:
        return {
            "job": self.job.to_dict(),
            "total_input": self.total_input,
            "n_processed": self.n_processed,
            "n_failed": self.n_failed,
            "ranked": [c.to_dict() for c in self.ranked],
            "failures": self.failures,
        }

    def to_dataframe(self):
        """
        Convenience: return a Pandas DataFrame for quick display.

        Only imports pandas at call time — the rest of the pipeline
        does not need it.
        """
        import pandas as pd

        return pd.DataFrame([c.candidate.summary_row() for c in self.ranked])


# ---------------------------------------------------------------------------
# Input collection
# ---------------------------------------------------------------------------

def _collect_pdf_paths(paths: list[str | Path]) -> list[Path]:
    """Expand directories into their .pdf files. Preserves input order."""
    out: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            out.extend(sorted(path.glob("*.pdf")))
        elif path.suffix.lower() == ".pdf" and path.exists():
            out.append(path)
        else:
            logger.warning("Skipping non-PDF or missing path: %s", path)
    return out


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_batch(
    pdf_paths: list[str | Path],
    job: JobRequirements | str,
    *,
    allow_ocr: bool = True,
    weights: dict[str, float] | None = None,
) -> BatchResult:
    """
    Run the full pipeline on a batch of resumes.

    Parameters
    ----------
    pdf_paths : list[str | Path]
        Files and/or directories. Directories are expanded to *.pdf.
    job : JobRequirements | str
        Either a pre-parsed JobRequirements, or raw JD text (auto-parsed).
    allow_ocr : bool
        Enable OCR fallback for scanned PDFs.
    weights : dict[str, float] | None
        Override SCORE_WEIGHTS from settings for this batch only.

    Returns
    -------
    BatchResult
        Contains the ranked list, any failures, and a copy of the job.
    """
    # ---- Normalize job ----------------------------------------------
    if isinstance(job, str):
        job = parse_job_description(job)
    if not job.raw_text:
        raise ValueError("Job description is empty")

    # ---- Collect inputs ---------------------------------------------
    paths = _collect_pdf_paths(list(pdf_paths))
    if not paths:
        logger.warning("No PDFs to process")
        return BatchResult(job=job, total_input=0)

    if len(paths) > settings.MAX_RESUMES_PER_BATCH:
        raise ValueError(
            f"Too many resumes ({len(paths)} > {settings.MAX_RESUMES_PER_BATCH}). "
            "Split into smaller batches."
        )

    logger.info("Processing %d resumes", len(paths))

    # ---- Phase 1: extraction (per resume) ---------------------------
    processed: list[ProcessedResume] = []
    failures: list[dict] = []

    for i, path in enumerate(paths, start=1):
        logger.debug("Extracting %d/%d: %s", i, len(paths), path.name)
        try:
            r = process_resume(path, job, allow_ocr=allow_ocr)
        except Exception as exc:  # noqa: BLE001 — defense in depth
            logger.exception("Unexpected error on %s", path.name)
            failures.append({
                "filename": path.name,
                "file_path": str(path),
                "error": f"Unexpected: {exc}",
            })
            continue

        if r.error:
            failures.append({
                "filename": r.filename,
                "file_path": r.file_path,
                "error": r.error,
            })
        else:
            processed.append(r)

    if not processed:
        logger.warning("All resumes failed to process")
        return BatchResult(
            job=job, failures=failures, total_input=len(paths),
        )

    # ---- Phase 2: scoring (batched) ---------------------------------
    scoring_input = {
        r.candidate_id: {
            "text": r.raw_text,
            "skills": r.skills,
            "years": r.total_years,
        }
        for r in processed
    }

    scores = score_batch(
        jd_text=job.raw_text,
        resumes=scoring_input,
        required_skills=job.required_skills,
        required_years=job.required_years,
        title_skills=job.title_skills,
        weights=weights,
    )

    # ---- Phase 3: rank & assemble -----------------------------------
    # Sort key: None scores at bottom, tie-break by name for determinism.
    def sort_key(r: ProcessedResume) -> tuple:
        sb = scores.get(r.candidate_id)
        val = sb.final if sb and sb.final is not None else -1.0
        return (-val, r.display_name)

    ordered = sorted(processed, key=sort_key)

    ranked: list[RankedCandidate] = []
    for rank, resume in enumerate(ordered, start=1):
        sb = scores.get(resume.candidate_id)
        if sb is None:
            continue

        # Build the display-ready candidate
        cand = resume.to_candidate()

        # Flatten the score into a JSON-safe view
        sv = to_score_view(sb)

        # Enrich the candidate with score-related fields
        cand.matched_skills = sv.matched_skills
        cand.missing_skills = sv.missing_skills
        cand.score = sv.final
        cand.display_score = sv.display_score
        cand.rank = rank
        cand.recommended_for_review = sv.recommended_for_review
        cand.extras["score_detail"] = sv.to_dict()

        ranked.append(RankedCandidate(rank=rank, candidate=cand, score=sv))

    logger.info(
        "Batch complete: %d ranked, %d failed",
        len(ranked), len(failures),
    )

    return BatchResult(
        job=job,
        ranked=ranked,
        failures=failures,
        total_input=len(paths),
    )