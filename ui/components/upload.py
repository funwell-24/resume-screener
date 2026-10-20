"""
Input collection: job description + resume PDFs.

Returns *typed* results (JobDescription, list of (filename, bytes)),
not widgets. All validation errors surface as st.error() with the
message from src.utils.validators, so the UX matches the backend.

Two paths supported:
    1. Paste JD text  (simplest, works for demo)
    2. Upload a .txt JD file
    …plus a file uploader for PDFs (accepts many at once).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import streamlit as st

from config import settings
from src.utils import validate_jd_text, ValidationError
from ui.styles import CSS_CLASSES


@dataclass
class UploadPayload:
    """What the uploader produced — validated and ready to hand off."""
    jd_text: str
    pdf_files: list[tuple[str, bytes]]      # (filename, content)


def render_jd_input() -> str | None:
    """
    Render the JD input area. Returns validated JD text, or None if
    the user hasn't provided usable input yet.
    """
    st.markdown(
        f"<div class='{CSS_CLASSES['section_title']}'>1. Job description</div>",
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "How would you like to provide the job description?",
        options=["Paste text", "Upload .txt file"],
        horizontal=True,
        label_visibility="collapsed",
        key="jd_input_mode",
    )

    jd_text = ""

    if mode == "Paste text":
        jd_text = st.text_area(
            "Paste the job description",
            height=220,
            placeholder=(
                "e.g. Senior Python Data Engineer\n\n"
                "Required: Python, pandas, SQL, AWS, Docker, scikit-learn\n"
                "Minimum 3 years of experience building data pipelines."
            ),
            key="jd_text_area",
        )
    else:
        uploaded = st.file_uploader(
            "Upload a .txt job description",
            type=["txt"],
            key="jd_file_upload",
        )
        if uploaded is not None:
            try:
                jd_text = uploaded.read().decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read file: {exc}")
                return None

    if not jd_text.strip():
        return None

    try:
        return validate_jd_text(jd_text)
    except ValidationError as exc:
        st.error(f"❌ {exc}")
        return None


def render_resume_upload() -> list[tuple[str, bytes]]:
    """
    Render the resume uploader. Returns list of (filename, bytes) for
    PDFs only — extension and magic-byte validation happen in the
    pipeline. We do a light pre-check here for UX (filter by extension).
    """
    st.markdown(
        f"<div class='{CSS_CLASSES['section_title']}'>2. Candidate resumes</div>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Upload PDF resumes (multiple allowed)",
        type=["pdf"],
        accept_multiple_files=True,
        key="resume_uploader",
    )

    if not uploaded:
        return []

    payload: list[tuple[str, bytes]] = []
    seen: set[str] = set()

    for f in uploaded:
        name = f.name
        if name in seen:
            continue
        seen.add(name)
        try:
            content = f.read()
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Skipping {name}: could not read file ({exc})")
            continue

        if not content:
            st.warning(f"Skipping {name}: file is empty")
            continue

        if not content.startswith(b"%PDF-"):
            st.warning(f"Skipping {name}: not a valid PDF (missing PDF header)")
            continue

        payload.append((name, content))

    # Size summary
    if payload:
        total_mb = sum(len(b) for _, b in payload) / (1024 * 1024)
        st.caption(
            f"{len(payload)} PDF(s) ready · {total_mb:.1f} MB total · "
            f"limit {settings.MAX_RESUMES_PER_BATCH} per batch"
        )

        if len(payload) > settings.MAX_RESUMES_PER_BATCH:
            st.error(
                f"Too many files ({len(payload)} > "
                f"{settings.MAX_RESUMES_PER_BATCH}). "
                f"Please split into smaller batches."
            )
            return []

    return payload


def render_sidebar_settings() -> dict:
    """
    Optional settings sidebar: OCR toggle, score weights override.

    Returns a dict of settings to thread into `run_batch`.
    """
    with st.sidebar:
        st.markdown("### Settings")
        allow_ocr = st.checkbox(
            "Allow OCR for scanned PDFs",
            value=True,
            help="Slower, but recovers text from image-only PDFs.",
        )

        with st.expander("Advanced: score weights"):
            st.caption(
                "Adjust how much each signal contributes to the final score. "
                "Weights must sum to 1.0."
            )
            kw = st.slider(
                "Skill overlap", 0.0, 1.0,
                value=settings.SCORE_WEIGHTS["keyword"], step=0.05,
            )
            sim = st.slider(
                "Similarity to JD", 0.0, 1.0,
                value=settings.SCORE_WEIGHTS["similarity"], step=0.05,
            )
            exp = st.slider(
                "Years of experience", 0.0, 1.0,
                value=settings.SCORE_WEIGHTS["experience"], step=0.05,
            )
            total = round(kw + sim + exp, 2)

            if abs(total - 1.0) > 0.01:
                st.warning(f"Weights sum to {total:.2f} (must be 1.00)")
                custom_weights = None
            else:
                custom_weights = {
                    "keyword": kw, "similarity": sim, "experience": exp,
                }

        st.markdown("---")
        st.caption(
            "☝️ This tool does **not** make hiring decisions. "
            "Scores are decision-support only."
        )

    return {
        "allow_ocr": allow_ocr,
        "weights": custom_weights,
    }