"""
Reporting: turn BatchMetrics / comparison results into display tables.

Two main reports:

    1. skill_extraction_report(metrics) -> str
       Text report for the terminal or a Markdown cell.

    2. comparison_report(tfidf_results, semantic_results) -> DataFrame
       Side-by-side TF-IDF vs. semantic scores.

    3. save_json / load_json
       Persist evaluation results to data/labeled/ for reproducibility.

All functions are pure (except save/load) — no printing, no side effects
in the compute path. Callers decide where to display.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .metrics import BatchMetrics, SetMetrics


# ---------------------------------------------------------------------------
# Text report
# ---------------------------------------------------------------------------

def skill_extraction_report(metrics: BatchMetrics) -> str:
    """
    Human-readable multi-line report for skill extraction evaluation.

    Suitable for pasting directly into your project README or a
    Streamlit `st.code(...)` block.
    """
    if metrics.n_candidates == 0:
        return "No candidates evaluated."

    lines = [
        "=" * 64,
        "SKILL EXTRACTION EVALUATION",
        "=" * 64,
        f"Candidates evaluated: {metrics.n_candidates}",
        "",
        "Aggregate metrics:",
        f"  Precision (macro): {metrics.macro_precision:.3f}",
        f"  Recall    (macro): {metrics.macro_recall:.3f}",
        f"  F1        (macro): {metrics.macro_f1:.3f}",
        f"  Precision (micro): {metrics.micro_precision:.3f}",
        f"  Recall    (micro): {metrics.micro_recall:.3f}",
        f"  F1        (micro): {metrics.micro_f1:.3f}",
        "",
        f"Confusion counts:",
        f"  TP: {metrics.total_tp}  FP: {metrics.total_fp}  FN: {metrics.total_fn}",
        "",
        "=" * 64,
        "PER-CANDIDATE BREAKDOWN",
        "=" * 64,
    ]

    # Sort by F1 ascending so the worst cases appear first
    ordered = sorted(
        metrics.per_candidate.items(),
        key=lambda kv: kv[1].f1,
    )

    for name, m in ordered:
        lines.append(f"\n{name}")
        lines.append(
            f"  P={m.precision:.2f}  R={m.recall:.2f}  F1={m.f1:.2f}  "
            f"(TP={m.tp} FP={m.fp} FN={m.fn})"
        )
        if m.false_positives:
            lines.append(f"  ✗ False positives: {m.false_positives}")
        if m.false_negatives:
            lines.append(f"  ✗ False negatives: {m.false_negatives}")

    lines.append("\n" + "=" * 64)
    return "\n".join(lines)


def worst_cases(
    metrics: BatchMetrics,
    n: int = 3,
) -> list[tuple[str, SetMetrics]]:
    """Return the n worst-performing candidates by F1."""
    ordered = sorted(
        metrics.per_candidate.items(),
        key=lambda kv: kv[1].f1,
    )
    return ordered[:n]


# ---------------------------------------------------------------------------
# Comparison report (TF-IDF vs semantic)
# ---------------------------------------------------------------------------

def comparison_report(
    tfidf_results: dict[str, float | None],
    semantic_results: dict[str, float | None],
):
    """
    Compare two scoring methods side-by-side.

    Parameters
    ----------
    tfidf_results, semantic_results : dict[str, float | None]
        {candidate_id: score in [0, 1] or None}

    Returns
    -------
    pandas.DataFrame
        Columns: Candidate, TF-IDF, Semantic, Δ (semantic − tfidf)
    """
    import pandas as pd

    keys = sorted(set(tfidf_results) | set(semantic_results))
    rows = []
    for k in keys:
        t = tfidf_results.get(k)
        s = semantic_results.get(k)
        delta = None if (t is None or s is None) else round(s - t, 4)
        rows.append({
            "Candidate": k,
            "TF-IDF": round(t, 4) if t is not None else None,
            "Semantic": round(s, 4) if s is not None else None,
            "Δ (sem − tfidf)": delta,
        })

    df = pd.DataFrame(rows)

    # Add a summary row
    valid_t = [t for t in tfidf_results.values() if t is not None]
    valid_s = [s for s in semantic_results.values() if s is not None]
    if valid_t and valid_s:
        summary = {
            "Candidate": "── MEAN ──",
            "TF-IDF": round(sum(valid_t) / len(valid_t), 4),
            "Semantic": round(sum(valid_s) / len(valid_s), 4),
            "Δ (sem − tfidf)": round(
                (sum(valid_s) / len(valid_s)) - (sum(valid_t) / len(valid_t)),
                4,
            ),
        }
        df = pd.concat([df, pd.DataFrame([summary])], ignore_index=True)

    return df


def ranking_agreement_report(
    tfidf_results: dict[str, float | None],
    semantic_results: dict[str, float | None],
    top_k: int = 5,
):
    """
    Compare the top-K rankings produced by two scoring methods.

    Returns a DataFrame with:
        - Rank, TF-IDF top-K, Semantic top-K
        - Whether each rank's candidate matches
        - The K % overlap (a measure of agreement)
    """
    import pandas as pd

    def _rank(results: dict[str, float | None]) -> list[str]:
        valid = [(k, v) for k, v in results.items() if v is not None]
        return [k for k, _ in sorted(valid, key=lambda kv: -kv[1])]

    tfidf_rank = _rank(tfidf_results)
    sem_rank = _rank(semantic_results)

    rows = []
    for i in range(top_k):
        a = tfidf_rank[i] if i < len(tfidf_rank) else None
        b = sem_rank[i] if i < len(sem_rank) else None
        rows.append({
            "Rank": i + 1,
            "TF-IDF": a,
            "Semantic": b,
            "Match": "✓" if a == b else "",
        })

    top_tfidf = set(tfidf_rank[:top_k])
    top_sem = set(sem_rank[:top_k])
    overlap = len(top_tfidf & top_sem)

    df = pd.DataFrame(rows)
    df.attrs["overlap"] = f"{overlap}/{top_k} overlap in top-{top_k}"
    return df


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_json(obj: Any, path: str | Path) -> None:
    """Save any serializable evaluation result."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
    elif hasattr(obj, "__dataclass_fields__"):
        data = asdict(obj)
    else:
        data = obj

    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_labeled_set(path: str | Path) -> dict[str, list[str]]:
    """
    Load a labeled test set from JSON.

    Expected format:
        {
          "alice_cv.pdf": ["python", "pandas", "sql"],
          "bob_cv.pdf":   ["java", "spring", "aws"]
        }
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Labeled set not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(
            f"Labeled set must be a JSON object, got {type(data).__name__}"
        )

    out: dict[str, list[str]] = {}
    for filename, skills in data.items():
        if not isinstance(skills, list):
            raise ValueError(
                f"Skills for {filename} must be a list, got {type(skills).__name__}"
            )
        out[filename] = [str(s).lower().strip() for s in skills if str(s).strip()]

    return out