"""
Evaluation metrics: precision, recall, F1 (set-based).

Used to score the skill extractor against a hand-labeled test set:

    gold = {"python", "pandas"}                       # what a human labeled
    pred = {"python", "sql"}                          # what extract_skills() found

    TP = {"python"}
    FP = {"sql"}
    FN = {"pandas"}

    precision = |TP| / (|TP| + |FP|) = 1/2 = 0.50
    recall    = |TP| / (|TP| + |FN|) = 1/2 = 0.50
    F1        = 2 * P * R / (P + R)  = 0.50

Handles edge cases:
    - Empty gold AND empty pred → perfect (1.0) — no skills claimed, none required
    - Empty gold only             → recall=1.0, precision=0.0 (any prediction is FP)
    - Empty pred only             → precision=1.0, recall=0.0 (nothing was missed because nothing was claimed... arguably 0.0 recall is correct)

Also provides:
    - Per-candidate metrics, then macro + micro averages over a batch
    - Confusion-style breakdown for reporting
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Iterable


@dataclass
class SetMetrics:
    """Metrics for a single comparison (one candidate)."""

    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    tp: int = 0
    fp: int = 0
    fn: int = 0

    n_gold: int = 0
    n_pred: int = 0

    # The sets themselves for traceability
    true_positives: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BatchMetrics:
    """Aggregate metrics over a set of candidates."""

    # Macro-average (average of per-candidate P/R/F1)
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0

    # Micro-average (aggregate TP/FP/FN first, then compute)
    micro_precision: float = 0.0
    micro_recall: float = 0.0
    micro_f1: float = 0.0

    # Totals
    n_candidates: int = 0
    total_tp: int = 0
    total_fp: int = 0
    total_fn: int = 0

    # Per-candidate breakdown
    per_candidate: dict[str, SetMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["per_candidate"] = {
            k: v.to_dict() for k, v in self.per_candidate.items()
        }
        return d

    def summary_row(self) -> dict:
        """One-line summary for a report table."""
        return {
            "Candidates": self.n_candidates,
            "Precision (macro)": round(self.macro_precision, 3),
            "Recall (macro)":    round(self.macro_recall, 3),
            "F1 (macro)":        round(self.macro_f1, 3),
            "Precision (micro)": round(self.micro_precision, 3),
            "Recall (micro)":    round(self.micro_recall, 3),
            "F1 (micro)":        round(self.micro_f1, 3),
            "TP": self.total_tp,
            "FP": self.total_fp,
            "FN": self.total_fn,
        }


# ---------------------------------------------------------------------------
# Single-comparison metric
# ---------------------------------------------------------------------------

def _normalize(s: Iterable[str]) -> set[str]:
    return {x.strip().lower() for x in s if x and str(x).strip()}


def compute_set_metrics(
    gold: Iterable[str],
    pred: Iterable[str],
) -> SetMetrics:
    """
    Precision / recall / F1 between two sets of skill names.

    Both sides are normalized (lowercase, stripped).
    """
    g = _normalize(gold)
    p = _normalize(pred)

    tp_set = g & p
    fp_set = p - g
    fn_set = g - p

    tp, fp, fn = len(tp_set), len(fp_set), len(fn_set)

    # Edge cases ------------------------------------------------------
    if tp == 0 and fp == 0 and fn == 0:
        # Both empty — vacuously perfect
        return SetMetrics(
            precision=1.0, recall=1.0, f1=1.0,
            tp=0, fp=0, fn=0, n_gold=0, n_pred=0,
        )

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    return SetMetrics(
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        tp=tp, fp=fp, fn=fn,
        n_gold=len(g), n_pred=len(p),
        true_positives=sorted(tp_set),
        false_positives=sorted(fp_set),
        false_negatives=sorted(fn_set),
    )


# ---------------------------------------------------------------------------
# Batch aggregate
# ---------------------------------------------------------------------------

def aggregate_metrics(
    per_candidate: dict[str, SetMetrics],
) -> BatchMetrics:
    """
    Aggregate per-candidate metrics into macro and micro averages.

    Macro: average P/R/F1 across candidates (treats every candidate equally).
    Micro: sum TP/FP/FN first, then compute (treats every skill equally).
    """
    if not per_candidate:
        return BatchMetrics()

    n = len(per_candidate)

    # Macro
    macro_p = sum(m.precision for m in per_candidate.values()) / n
    macro_r = sum(m.recall for m in per_candidate.values()) / n
    macro_f1 = sum(m.f1 for m in per_candidate.values()) / n

    # Micro
    tp = sum(m.tp for m in per_candidate.values())
    fp = sum(m.fp for m in per_candidate.values())
    fn = sum(m.fn for m in per_candidate.values())

    micro_p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    micro_r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    micro_f1 = (
        2 * micro_p * micro_r / (micro_p + micro_r)
        if (micro_p + micro_r) > 0 else 0.0
    )

    return BatchMetrics(
        macro_precision=round(macro_p, 4),
        macro_recall=round(macro_r, 4),
        macro_f1=round(macro_f1, 4),
        micro_precision=round(micro_p, 4),
        micro_recall=round(micro_r, 4),
        micro_f1=round(micro_f1, 4),
        n_candidates=n,
        total_tp=tp, total_fp=fp, total_fn=fn,
        per_candidate=per_candidate,
    )


# ---------------------------------------------------------------------------
# End-to-end evaluator against a labeled set
# ---------------------------------------------------------------------------

def evaluate_skill_extraction(
    labeled_set: dict[str, list[str]],
    extractor,  # callable: (pdf_path) -> set[str]
    pdf_dir: "str | Path",
) -> BatchMetrics:
    """
    Run the extractor on each labeled resume and compute metrics.

    Parameters
    ----------
    labeled_set : dict[str, list[str]]
        {filename: [gold_skill1, gold_skill2, ...]}
    extractor : callable
        A function taking a path and returning a set of skills.
        Typically: lambda p: extract_skills(parse_pdf(p))
    pdf_dir : str | Path
        Directory where the labeled PDFs live.

    Returns
    -------
    BatchMetrics
        Aggregated results, including per-candidate breakdown.
    """
    from pathlib import Path
    pdf_dir = Path(pdf_dir)

    per_candidate: dict[str, SetMetrics] = {}

    for filename, gold_skills in labeled_set.items():
        pdf_path = pdf_dir / filename
        if not pdf_path.exists():
            per_candidate[filename] = SetMetrics(
                # Missing file → count as total miss
                precision=0.0,
                recall=0.0,
                f1=0.0,
                tp=0, fp=0, fn=len(gold_skills),
                n_gold=len(gold_skills), n_pred=0,
                false_negatives=sorted(set(s.lower() for s in gold_skills)),
            )
            continue

        try:
            pred = extractor(pdf_path)
        except Exception:  # noqa: BLE001
            pred = set()

        per_candidate[filename] = compute_set_metrics(gold_skills, pred)

    return aggregate_metrics(per_candidate)