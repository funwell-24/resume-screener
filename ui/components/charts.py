"""
Score distribution visualizations.

Two charts:
    render_score_distribution(result)  → histogram of scores
    render_skill_gap_chart(result)     → horizontal bar of most-missed skills

Both use Matplotlib for full control (Streamlit's built-in charts don't
support the styling we need). Imported lazily so the rest of the app
runs even if Matplotlib isn't installed.
"""

from __future__ import annotations

from collections import Counter

import streamlit as st

from src.pipeline import BatchResult
from ui.styles import COLORS


def render_score_distribution(result: BatchResult) -> None:
    """Histogram of candidate scores with band coloring."""
    if result.n_processed < 2:
        return  # not enough data for a meaningful distribution

    import matplotlib.pyplot as plt
    import numpy as np

    scores = [
        c.candidate.display_score
        for c in result.ranked
        if c.candidate.display_score is not None
    ]
    if not scores:
        return

    st.markdown("#### Score distribution")

    fig, ax = plt.subplots(figsize=(8, 3.2))

    # Color bins by band
    bins = np.arange(0, 101, 10)
    counts, edges = np.histogram(scores, bins=bins)

    bar_colors = []
    for edge in edges[:-1]:
        if edge >= 75:
            bar_colors.append(COLORS["success"])
        elif edge >= 50:
            bar_colors.append(COLORS["warning"])
        else:
            bar_colors.append(COLORS["danger"])

    ax.bar(
        edges[:-1], counts, width=8,
        color=bar_colors, edgecolor="white", linewidth=0.5,
    )

    # Mean line
    mean = sum(scores) / len(scores)
    ax.axvline(
        mean, color=COLORS["primary"],
        linestyle="--", linewidth=1.2,
        label=f"Mean: {mean:.1f}",
    )

    ax.set_xlabel("Score (0–100)")
    ax.set_ylabel("Candidates")
    ax.set_xticks(bins)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=0.25)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.caption(
        "🟢 ≥75 · 🟡 50–74 · 🔴 <50 · "
        "Scores are decision-support only — review each candidate manually."
    )


def render_skill_gap_chart(result: BatchResult, top_n: int = 10) -> None:
    """Horizontal bar chart of the most commonly missing skills."""
    if result.n_processed == 0:
        return

    missing_counter: Counter[str] = Counter()
    for rc in result.ranked:
        for skill in rc.score.missing_skills:
            missing_counter[skill] += 1

    if not missing_counter:
        st.info("No missing skills detected across this batch.")
        return

    top = missing_counter.most_common(top_n)
    skills = [s for s, _ in top][::-1]       # reverse for top-at-top
    counts = [c for _, c in top][::-1]

    st.markdown("#### Most commonly missing skills")

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.35 * len(skills))))
    ax.barh(
        skills, counts,
        color=COLORS["danger"], alpha=0.75,
        edgecolor="white", linewidth=0.5,
    )

    for i, v in enumerate(counts):
        ax.text(
            v + 0.1, i, str(v),
            va="center", fontsize=9, color=COLORS["neutral"],
        )

    ax.set_xlabel("Candidates missing this skill")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    st.caption(
        "Skills that most candidates are missing — useful for "
        "calibrating the JD's expectations."
    )