"""
AI Resume Screener - Streamlit entry point.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import tempfile
import traceback
from pathlib import Path

import streamlit as st

from config import settings
from src.pipeline import parse_job_description, run_batch, BatchResult
from src.utils import setup_logging, get_logger, safe_filename
from src.utils.validators import ValidationError
from ui import inject_custom_css
from ui.components import (
    render_disclaimer,
    render_footer_disclaimer,
    render_jd_input,
    render_resume_upload,
    render_sidebar_settings,
    render_summary_metrics,
    render_results_table,
    render_failures,
    render_candidate_list,
    render_score_distribution,
    render_skill_gap_chart,
)


st.set_page_config(
    page_title="AI Resume Screener",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded",
)

setup_logging()
logger = get_logger(__name__)

inject_custom_css()


def _ensure_state() -> None:
    if "batch_result" not in st.session_state:
        st.session_state.batch_result = None
    if "last_run_inputs" not in st.session_state:
        st.session_state.last_run_inputs = None
    if "is_running" not in st.session_state:
        st.session_state.is_running = False


def _render_results(result: BatchResult) -> None:
    render_summary_metrics(result)
    render_results_table(result)
    render_failures(result)
    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        render_score_distribution(result)
    with col_right:
        render_skill_gap_chart(result)
    st.markdown("---")
    render_candidate_list(result)
    st.markdown("---")
    render_footer_disclaimer()


def main() -> None:
    _ensure_state()

    st.title("AI Resume Screener")
    st.caption(
        "Rank candidates against a job description - "
        "with full explanations and human-in-the-loop review."
    )

    render_disclaimer()

    ui_settings = render_sidebar_settings()

    jd_text = render_jd_input()
    pdf_files = render_resume_upload()

    can_run = bool(jd_text) and bool(pdf_files) and not st.session_state.is_running

    col_run, col_clear, _spacer = st.columns([1, 1, 4])

    with col_run:
        run_clicked = st.button(
            "Screen candidates",
            type="primary",
            disabled=not can_run,
            use_container_width=True,
        )

    with col_clear:
        if st.button(
            "Clear results",
            disabled=st.session_state.batch_result is None,
            use_container_width=True,
        ):
            st.session_state.batch_result = None
            st.session_state.last_run_inputs = None
            st.rerun()

    if not can_run and not run_clicked:
        missing = []
        if not jd_text:
            missing.append("job description")
        if not pdf_files:
            missing.append("at least one PDF resume")
        if missing:
            st.info(f"Provide a {' and '.join(missing)} to enable screening.")

    if run_clicked and can_run:
        st.session_state.is_running = True
        result = None
        error = None

        with st.spinner(f"Parsing and scoring {len(pdf_files)} resume(s)..."):
            try:
                job = parse_job_description(jd_text)

                if not job.required_skills:
                    st.warning(
                        "The JD didn't yield any required skills. "
                        "Consider adding specific skills or extending "
                        "config/skills.json."
                    )

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_paths = []
                    for filename, content in pdf_files:
                        safe = safe_filename(filename)
                        dest = Path(tmpdir) / safe
                        dest.write_bytes(content)
                        tmp_paths.append(dest)

                    result = run_batch(
                        tmp_paths,
                        job,
                        allow_ocr=ui_settings["allow_ocr"],
                        weights=ui_settings.get("weights"),
                    )

            except ValidationError as exc:
                error = f"Input validation failed: {exc}"
            except Exception as exc:
                error = f"Something went wrong: {exc}"
                logger.exception("Pipeline failed during UI run")
                with st.expander("Show technical details"):
                    st.code(traceback.format_exc())
            finally:
                st.session_state.is_running = False

        if error:
            st.error(f"Error: {error}")
        elif result is not None:
            st.session_state.batch_result = result
            st.session_state.last_run_inputs = {
                "jd_chars": len(jd_text),
                "n_pdfs": len(pdf_files),
            }
            st.success(
                f"Processed {result.n_processed} candidate(s)"
                + (f" - {result.n_failed} failed" if result.n_failed else "")
            )

    if st.session_state.batch_result is not None:
        st.markdown("---")
        _render_results(st.session_state.batch_result)

    elif not run_clicked:
        st.markdown("---")
        st.markdown(
            """
            ### How to use

            1. **Paste or upload a job description** above.
            2. **Upload candidate PDF resumes** (multiple allowed).
            3. *(Optional)* Adjust settings in the sidebar.
            4. Click **Screen candidates**.

            You will see a ranked table, per-candidate breakdowns,
            and charts summarizing the batch.
            """
        )


if __name__ == "__main__":
    main()