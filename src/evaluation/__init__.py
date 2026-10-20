"""
Evaluation layer: measure how well the extractors actually work.

Public API:
    compute_set_metrics(gold, pred) -> SetMetrics
        Precision / recall / F1 for one candidate.

    aggregate_metrics({name: SetMetrics}) -> BatchMetrics
        Macro + micro averages.

    evaluate_skill_extraction(labeled_set, extractor, pdf_dir) -> BatchMetrics
        End-to-end: run the extractor over a labeled test set.

    skill_extraction_report(metrics) -> str
        Human-readable text report.

    comparison_report(tfidf_results, semantic_results) -> DataFrame
        Side-by-side TF-IDF vs semantic.

    ranking_agreement_report(tfidf_results, semantic_results) -> DataFrame
        Top-K overlap between two methods.

    save_json(obj, path) / load_labeled_set(path)
        Persistence.
"""

from .metrics import (
    SetMetrics,
    BatchMetrics,
    compute_set_metrics,
    aggregate_metrics,
    evaluate_skill_extraction,
)
from .reporter import (
    skill_extraction_report,
    worst_cases,
    comparison_report,
    ranking_agreement_report,
    save_json,
    load_labeled_set,
)

__all__ = [
    # Metrics
    "SetMetrics",
    "BatchMetrics",
    "compute_set_metrics",
    "aggregate_metrics",
    "evaluate_skill_extraction",
    # Reports
    "skill_extraction_report",
    "worst_cases",
    "comparison_report",
    "ranking_agreement_report",
    # Persistence
    "save_json",
    "load_labeled_set",
]