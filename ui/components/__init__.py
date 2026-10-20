"""
Streamlit components — thin, typed, side-effect-free wrappers.

Nothing here computes scores or business logic. Every function accepts
typed data from `src/` and renders UI.
"""

from .disclaimer import render_disclaimer, render_footer_disclaimer
from .upload import (
    UploadPayload,
    render_jd_input,
    render_resume_upload,
    render_sidebar_settings,
)
from .results_table import (
    render_summary_metrics,
    render_results_table,
    render_failures,
)
from .candidate_card import (
    render_candidate_detail,
    render_candidate_list,
)
from .charts import (
    render_score_distribution,
    render_skill_gap_chart,
)

__all__ = [
    # Disclaimer
    "render_disclaimer",
    "render_footer_disclaimer",
    # Upload
    "UploadPayload",
    "render_jd_input",
    "render_resume_upload",
    "render_sidebar_settings",
    # Results
    "render_summary_metrics",
    "render_results_table",
    "render_failures",
    # Candidates
    "render_candidate_detail",
    "render_candidate_list",
    # Charts
    "render_score_distribution",
    "render_skill_gap_chart",
]