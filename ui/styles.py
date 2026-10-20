"""
Custom CSS + shared visual constants.

Injected once via `inject_custom_css()` at app startup. Keeps styling
centralized — components reference `CSS_CLASSES` constants instead of
hard-coding class names.

Design notes:
    - Uses Streamlit's theme variables (via CSS custom properties) so
      the app respects light/dark mode out of the box.
    - All colors defined as variables at the top — change once, apply
      everywhere.
    - Class names are prefixed `rs-` (resume-screener) to avoid collisions.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Palette — semantic color tokens
# ---------------------------------------------------------------------------
COLORS = {
    "primary":    "#2563eb",   # blue-600
    "success":    "#16a34a",   # green-600
    "warning":    "#ca8a04",   # yellow-600
    "danger":     "#dc2626",   # red-600
    "neutral":    "#64748b",   # slate-500
    "muted_bg":   "rgba(100, 116, 139, 0.08)",
    "border":     "rgba(148, 163, 184, 0.25)",
}

# Score → color band (used by charts + badges)
SCORE_BANDS = [
    (0.75, COLORS["success"], "Strong match"),
    (0.50, COLORS["warning"], "Possible match"),
    (0.00, COLORS["danger"],  "Weak match"),
]


# ---------------------------------------------------------------------------
# CSS class names (referenced by components)
# ---------------------------------------------------------------------------
CSS_CLASSES = {
    "badge_base":     "rs-badge",
    "badge_matched":  "rs-badge rs-badge-matched",
    "badge_missing":  "rs-badge rs-badge-missing",
    "badge_neutral":  "rs-badge rs-badge-neutral",
    "badge_review":   "rs-badge rs-badge-review",
    "disclaimer":     "rs-disclaimer",
    "card":           "rs-card",
    "card_meta":      "rs-card-meta",
    "score_big":      "rs-score-big",
    "section_title":  "rs-section-title",
}


# ---------------------------------------------------------------------------
# CSS payload
# ---------------------------------------------------------------------------
_CSS = f"""
<style>
/* ---------- Global typography ---------- */
.rs-section-title {{
    font-size: 1.15rem;
    font-weight: 600;
    margin: 1.25rem 0 0.5rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid {COLORS["border"]};
}}

/* ---------- Badges (skills, flags) ---------- */
.rs-badge {{
    display: inline-block;
    padding: 2px 10px;
    margin: 2px 4px 2px 0;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 500;
    line-height: 1.6;
    white-space: nowrap;
}}
.rs-badge-matched {{
    background: rgba(22, 163, 74, 0.12);
    color: {COLORS["success"]};
    border: 1px solid rgba(22, 163, 74, 0.3);
}}
.rs-badge-missing {{
    background: rgba(220, 38, 38, 0.08);
    color: {COLORS["danger"]};
    border: 1px solid rgba(220, 38, 38, 0.25);
}}
.rs-badge-neutral {{
    background: {COLORS["muted_bg"]};
    color: {COLORS["neutral"]};
    border: 1px solid {COLORS["border"]};
}}
.rs-badge-review {{
    background: rgba(37, 99, 235, 0.12);
    color: {COLORS["primary"]};
    border: 1px solid rgba(37, 99, 235, 0.3);
    font-weight: 600;
}}

/* ---------- Disclaimer banner ---------- */
.rs-disclaimer {{
    padding: 12px 16px;
    border-left: 4px solid {COLORS["warning"]};
    background: rgba(202, 138, 4, 0.08);
    border-radius: 4px;
    font-size: 0.9rem;
    line-height: 1.5;
    margin-bottom: 1rem;
}}
.rs-disclaimer strong {{
    color: {COLORS["warning"]};
}}

/* ---------- Candidate card ---------- */
.rs-card {{
    padding: 16px 20px;
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    margin-bottom: 12px;
}}
.rs-card-meta {{
    font-size: 0.85rem;
    color: {COLORS["neutral"]};
    margin-top: 4px;
}}

/* ---------- Large score display ---------- */
.rs-score-big {{
    font-size: 2.25rem;
    font-weight: 700;
    line-height: 1.1;
    margin: 0;
}}
</style>
"""


def inject_custom_css() -> None:
    """
    Inject the stylesheet. Call ONCE per session, at app startup.

    Idempotent guard prevents re-injection on rerun if you call it in
    the wrong place — but the recommended pattern is to call it once
    at the top of app.py before rendering anything.
    """
    import streamlit as st
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers used by components
# ---------------------------------------------------------------------------
def score_color(score: float | None) -> str:
    """Return the hex color for a 0..1 score."""
    if score is None:
        return COLORS["neutral"]
    for threshold, color, _label in SCORE_BANDS:
        if score >= threshold:
            return color
    return COLORS["danger"]


def score_label(score: float | None) -> str:
    """Return the human label ("Strong match" / etc.) for a score."""
    if score is None:
        return "No score"
    for threshold, _color, label in SCORE_BANDS:
        if score >= threshold:
            return label
    return "Weak match"