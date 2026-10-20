"""
Typed data contracts for the whole pipeline.

Everything that flows between layers, into the UI, or into an export
should be expressed as one of these types. This is the single place
to look when you want to know "what shape is a candidate / job / score?"

Public API:
    Candidate       — one applicant, JSON-safe
    JobDescription  — the parsed job, JSON-safe
    ScoreView       — flattened, JSON-safe score breakdown
    ScoreBreakdown  — canonical score record (re-exported from scoring)

Conversions:
    ProcessedResume.to_candidate()   → Candidate
    JobRequirements.to_job_description() → JobDescription
    to_score_view(ScoreBreakdown)    → ScoreView
"""

from .candidate import Candidate
from .job import JobDescription
from .score import ScoreBreakdown, ScoreView, to_score_view

__all__ = [
    "Candidate",
    "JobDescription",
    "ScoreBreakdown",
    "ScoreView",
    "to_score_view",
]