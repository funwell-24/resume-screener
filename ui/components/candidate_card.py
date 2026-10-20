"""
Per-candidate detail view.

Two render modes:
    render_candidate_detail(candidate, score)   → single card for one
        candidate (used in a "detail" page or drill-down).
    render_candidate_list(result)               → expanders for every
        candidate, in rank order, so the recruiter can scan quickly.
"""

from __future__ import annotations

from typing import Iterable

import streamlit as st

from src.models import Candidate, ScoreView
from src.pipeline import BatchResult
from ui.styles import CSS_CLASSES, score_color, score_label


# ---------------------------------------------------------------------------
# Small badge helpers
# ---------------------------------------------------------------------------

def _badge(text: str, kind: str = "neutral") -> str:
    cls = {
        "matched": CSS_CLASSES["badge_matched"],
        "missing": CSS_CLASSES["badge_missing"],
        "neutral": CSS_CLASSES["badge_neutral"],
        "review":  CSS_CLASSES["badge_review"],
    }.get(kind, CSS_CLASSES["badge_neutral"])
    return f"<span class='{cls}'>{text}</span>"


def _skill_badges(skills: Iterable[str], kind: str) -> str:
    items = sorted(set(skills))
    if not items:
        return "<span style='opacity:0.5;font-size:0.85rem'>(none)</span>"
    return " ".join(_badge(s, kind) for s in items)


# ---------------------------------------------------------------------------
# Header (name, score, flag)
# ---------------------------------------------------------------------------

def _render_header(candidate: Candidate, score: ScoreView) -> None:
    color = score_color(score.final)
    label = score_label(score.final)

    col_left, col_right = st.columns([3, 1])

    with col_left:
        st.markdown(
            f"### #{candidate.rank} · {candidate.display_name}"
        )
        meta_bits = []
        if candidate.email:
            meta_bits.append(f"✉ {candidate.email}")
        if candidate.phone:
            meta_bits.append(f"☎ {candidate.phone}")
        if candidate.linkedin:
            meta_bits.append(f"[LinkedIn]({candidate.linkedin})")
        if candidate.github:
            meta_bits.append(f"[GitHub]({candidate.github})")
        if meta_bits:
            st.markdown(
                f"<div class='{CSS_CLASSES['card_meta']}'>"
                + " · ".join(meta_bits) + "</div>",
                unsafe_allow_html=True,
            )

    with col_right:
        display = (
            f"{score.display_score:.1f}"
            if score.display_score is not None else "–"
        )
        st.markdown(
            f"<div style='text-align:right'>"
            f"<p class='{CSS_CLASSES['score_big']}' style='color:{color}'>"
            f"{display}<span style='font-size:0.9rem;opacity:0.6'>/100</span>"
            f"</p>"
            f"<div style='font-size:0.85rem;color:{color};font-weight:600'>"
            f"{label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if score.recommended_for_review:
            st.markdown(
                f"<div style='text-align:right;margin-top:6px'>"
                f"{_badge('★ Flagged for review', 'review')}"
                f"</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------------------------

def _render_score_breakdown(score: ScoreView) -> None:
    st.markdown(
        f"<div class='{CSS_CLASSES['section_title']}'>Score breakdown</div>",
        unsafe_allow_html=True,
    )

    def _pct(x: float | None) -> str:
        return "—" if x is None else f"{x * 100:.0f}%"

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Skill overlap",
        _pct(score.keyword_score),
        help=f"{len(score.matched_skills)} of "
             f"{len(score.required_skills)} required skills matched",
    )
    c2.metric(
        "Text similarity",
        _pct(score.similarity_score),
        help="Cosine similarity between resume and JD text",
    )
    c3.metric(
        "Experience fit",
        _pct(score.experience_score),
        help=(
            f"{score.candidate_years:.1f}y vs. required "
            f"{score.required_years:.1f}y"
            if score.required_years is not None
            else "No years requirement in JD"
        ),
    )

    if score.explanation:
        st.caption(score.explanation)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def _render_skills(score: ScoreView) -> None:
    st.markdown(
        f"<div class='{CSS_CLASSES['section_title']}'>Skills</div>",
        unsafe_allow_html=True,
    )

    st.markdown("**Matched requirements**", unsafe_allow_html=True)
    st.markdown(
        _skill_badges(score.matched_skills, "matched"),
        unsafe_allow_html=True,
    )

    st.markdown("**Missing requirements**", unsafe_allow_html=True)
    st.markdown(
        _skill_badges(score.missing_skills, "missing"),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Extra metadata
# ---------------------------------------------------------------------------

def _render_metadata(candidate: Candidate, score: ScoreView) -> None:
    cols = st.columns(4)
    cols[0].metric("Years", f"{candidate.total_years:.1f}")
    cols[1].metric("Education", candidate.education_level.replace("_", " ").title())
    cols[2].metric("Pages", candidate.num_pages)
    cols[3].metric("OCR used", "Yes" if candidate.used_ocr else "No")

    extras_bits = []
    if candidate.education_institution:
        extras_bits.append(f"🎓 {candidate.education_institution}")
    if candidate.education_field:
        extras_bits.append(candidate.education_field.title())
    if candidate.n_jobs:
        extras_bits.append(f"{candidate.n_jobs} job(s) detected")

    if extras_bits:
        st.markdown(
            f"<div class='{CSS_CLASSES['card_meta']}'>"
            + " · ".join(extras_bits) + "</div>",
            unsafe_allow_html=True,
        )

    if score.top_shared_terms:
        terms = ", ".join(t for t, _ in score.top_shared_terms[:8])
        st.markdown(
            f"<div class='{CSS_CLASSES['card_meta']}'>"
            f"<strong>Top shared terms:</strong> {terms}</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_candidate_detail(candidate: Candidate, score: ScoreView) -> None:
    """Render a full detail card for one candidate."""
    with st.container():
        st.markdown(f"<div class='{CSS_CLASSES['card']}'>", unsafe_allow_html=True)
        _render_header(candidate, score)
        _render_metadata(candidate, score)
        _render_score_breakdown(score)
        _render_skills(score)
        st.markdown("</div>", unsafe_allow_html=True)


def render_candidate_list(result: BatchResult) -> None:
    """
    Render expandable cards for every candidate, in rank order.

    Only the top result is expanded by default — keeps the page scannable
    while a recruiter drills into anyone they want.
    """
    if result.n_processed == 0:
        st.info("No candidates to display.")
        return

    st.markdown(
        f"<div class='{CSS_CLASSES['section_title']}'>Candidates</div>",
        unsafe_allow_html=True,
    )

    for i, rc in enumerate(result.ranked):
        cand = rc.candidate
        score = rc.score

        header = (
            f"#{cand.rank}  ·  {cand.display_name}  ·  "
            f"{score.display_score if score.display_score is not None else '–'}/100"
            + ("  ·  ★ Review" if score.recommended_for_review else "")
        )

        with st.expander(header, expanded=(i == 0)):
            _render_header(cand, score)
            _render_metadata(cand, score)
            _render_score_breakdown(score)
            _render_skills(score)

            # Show full extracted text in a collapsed sub-expander
            with st.expander("Raw extracted text", expanded=False):
                # The pipeline carries raw_text; expose it via extras if present
                raw = cand.extras.get("raw_text")
                if raw:
                    st.text(raw)
                else:
                    st.caption(
                        "Raw text not available in this view. "
                        "It's preserved in the pipeline's ProcessedResume object."
                    )