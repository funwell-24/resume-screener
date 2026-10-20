"""
The ethics banner. Renders on every page — non-negotiable.

Two render modes:
    render_disclaimer()       → full banner with title + text
    render_footer_disclaimer() → compact one-liner for the bottom
"""

from __future__ import annotations

import streamlit as st

from ui.styles import CSS_CLASSES


_DISCLAIMER_HTML = f"""
<div class="{CSS_CLASSES['disclaimer']}">
<strong>⚠️ Human review required.</strong>
This tool produces an <em>aid</em> for screening, not a decision.
Match scores are computed from keyword overlap and text similarity —
they can miss relevant experience, misjudge transferable skills, and
penalize non-standard resume formats. <strong>Do not use these scores
to automatically reject or rank candidates.</strong> Every candidate
should be reviewed by a human before any action is taken.
</div>
"""

_FOOTER_HTML = (
    "Scores are decision-support only — "
    "<strong>always review candidates manually</strong>."
)


def render_disclaimer() -> None:
    """Full disclaimer banner for the top of the app."""
    st.markdown(_DISCLAIMER_HTML, unsafe_allow_html=True)


def render_footer_disclaimer() -> None:
    """Compact disclaimer for the bottom of results pages."""
    st.markdown(
        f"<div class='{CSS_CLASSES['card_meta']}'>{_FOOTER_HTML}</div>",
        unsafe_allow_html=True,
    )