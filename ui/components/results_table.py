"""
Ranked results table + summary metrics.

Renders a Pandas DataFrame from `BatchResult.ranked`. Uses Streamlit's
`st.dataframe` with column config for:
    - Score column colored by band
    - Review flag as a badge column
    - Column widths tuned for readability

Also exposes `render_summary_metrics` — top-line stats (n processed,
n failed, mean score, top match) shown above the table.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.pipeline import BatchResult
from ui.styles import CSS_CLASSES, score_color


def render_summary_metrics(result: BatchResult) -> None:
    """Top-line stats — 4 metric cards across the top of the results page."""
    if result.n_processed == 0:
        return

    scores = [
        c.candidate.display_score
        for c in result.ranked
        if c.candidate.display_score is not None
    ]
    mean_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    top = result.ranked[0].candidate

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Processed", result.n_processed)
    c2.metric("Failed", result.n_failed)
    c3.metric("Mean score", f"{mean_score}/100")
    c4.metric(
        "Top match",
        top.display_name,
        delta=f"{top.display_score}/100",
    )

    st.markdown("---")


def _rows_dataframe(result: BatchResult) -> pd.DataFrame:
    """Build a display DataFrame from BatchResult."""
    rows = []
    for rc in result.ranked:
        c = rc.candidate
        rows.append({
            "Rank": c.rank,
            "Candidate": c.display_name,
            "Score": c.display_score,
            "Review": "✓" if c.recommended_for_review else "",
            "Matched": len(c.matched_skills),
            "Missing": len(c.missing_skills),
            "Years": round(c.total_years, 1),
            "Education": c.education_level.replace("_", " ").title(),
            "File": c.filename,
        })
    return pd.DataFrame(rows)


def render_results_table(result: BatchResult) -> None:
    """
    Render the ranked table with styling.

    Uses st.dataframe's column_config for:
        - Progress-bar on the score
        - Hidden file column by default
    """
    if result.n_processed == 0:
        st.info("No successfully processed resumes to display.")
        return

    df = _rows_dataframe(result)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score (0–100)",
                help="Weighted combination of skill overlap, similarity, "
                     "and years of experience. Decision-support only.",
                min_value=0.0,
                max_value=100.0,
                format="%.1f",
            ),
            "Rank": st.column_config.NumberColumn(
                "Rank", width="small", format="%d",
            ),
            "Review": st.column_config.TextColumn(
                "Review", width="small",
                help="Flagged for recruiter review if score ≥ 60/100",
            ),
            "Matched": st.column_config.NumberColumn(
                "Matched", width="small",
                help="Number of JD-required skills present in the resume",
            ),
            "Missing": st.column_config.NumberColumn(
                "Missing", width="small",
                help="Number of JD-required skills not found in the resume",
            ),
            "Years": st.column_config.NumberColumn(
                "Years", width="small", format="%.1f",
            ),
            "Education": st.column_config.TextColumn(
                "Education", width="small",
            ),
            "File": st.column_config.TextColumn(
                "File", width="medium",
            ),
        },
        key="results_table",
    )


def render_failures(result: BatchResult) -> None:
    """Show failed PDFs in a collapsible expander (never hidden entirely)."""
    if not result.failures:
        return

    with st.expander(
        f"⚠️ {len(result.failures)} file(s) could not be processed",
        expanded=False,
    ):
        df = pd.DataFrame(result.failures)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(
            "Common causes: scanned PDF with no OCR text, password-protected "
            "file, or an unsupported layout."
        )