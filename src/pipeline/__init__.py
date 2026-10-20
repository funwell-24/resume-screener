"""
Pipeline orchestration layer.

Public API:
    parse_job_description(text) -> JobRequirements
    process_resume(pdf_path, job) -> ProcessedResume
    run_batch(pdf_paths, job) -> BatchResult
"""

from .jd_parser import (
    JobRequirements,
    parse_job_description,
    parse_job_description_file,
)
from .resume_pipeline import ProcessedResume, process_resume
from .batch_runner import (
    BatchResult,
    RankedCandidate,
    run_batch,
)

__all__ = [
    # Job
    "JobRequirements",
    "parse_job_description",
    "parse_job_description_file",
    # Single resume
    "ProcessedResume",
    "process_resume",
    # Batch
    "BatchResult",
    "RankedCandidate",
    "run_batch",
]