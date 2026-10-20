"""
PDF text extraction using PyMuPDF (fitz).

Strategy:
    1. Open PDF, iterate pages, try get_text("text") â€” fastest, most accurate.
    2. If a page returns too little text, retry with get_text("blocks")
       (helps with multi-column layouts).
    3. If the whole document is suspiciously short, flag it for OCR fallback.
    4. Always return cleaned text (see cleaner.py).

Design notes:
    - Never raises on a single bad page â€” logs and continues.
    - Caller decides whether to OCR (we just expose `needs_ocr`).
    - No OCR dependency imported here â€” kept in ocr_fallback.py so
      users without Tesseract installed can still use the tool.
"""

from __future__ import annotations

import logging
from pathlib import Path

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:          # pragma: no cover — fallback for older installs
    import fitz              # type: ignore[no-redef]

from .cleaner import clean_text

logger = logging.getLogger(__name__)

# Heuristics: a resume page with fewer than this many chars per page
# is almost certainly a scanned image.
MIN_CHARS_PER_PAGE = 100

# Refuse absurdly large files early (defensive)
MAX_FILE_SIZE_MB = 25


def _extract_page_text(page: "fitz.Page") -> str:
    """
    Extract text from a single page with a fallback strategy.

    Try plain text mode first (fastest, preserves reading order for
    simple layouts). If that yields too little, try block mode, which
    sometimes does better on multi-column resumes.
    """
    text = page.get_text("text") or ""
    if len(text.strip()) >= MIN_CHARS_PER_PAGE:
        return text

    # Fallback: block mode. Sort blocks by (y, x) for natural reading order.
    blocks = page.get_text("blocks") or []
    # Each block is (x0, y0, x1, y1, text, block_no, block_type)
    text_blocks = [b for b in blocks if len(b) >= 5 and b[4].strip()]
    text_blocks.sort(key=lambda b: (round(b[1]), b[0]))
    block_text = "\n".join(b[4] for b in text_blocks)

    # Use whichever is longer
    return block_text if len(block_text) > len(text) else text


def parse_pdf(path: str | Path) -> str:
    """
    Extract cleaned text from a PDF file.

    Parameters
    ----------
    path : str | Path
        Path to the PDF file.

    Returns
    -------
    str
        Cleaned text. Empty string if the file cannot be read or has
        no extractable text (likely scanned â€” caller should OCR it).
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {path}")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large ({size_mb:.1f} MB > {MAX_FILE_SIZE_MB} MB): {path.name}"
        )

    parts: list[str] = []

    try:
        with fitz.open(path) as doc:
            if doc.is_encrypted:
                logger.warning("Encrypted PDF (attempting open): %s", path.name)
                # Empty password sometimes works for "owner" passwords
                if not doc.authenticate(""):
                    logger.error("Cannot decrypt PDF: %s", path.name)
                    return ""

            for page_num, page in enumerate(doc, start=1):
                try:
                    page_text = _extract_page_text(page)
                    if page_text.strip():
                        parts.append(page_text)
                except Exception as exc:  # noqa: BLE001 â€” one bad page shouldn't kill the doc
                    logger.warning(
                        "Failed to extract page %d of %s: %s",
                        page_num, path.name, exc,
                    )
                    continue
    except Exception as exc:  # noqa: BLE001 â€” corrupt PDFs are common
        logger.error("Failed to open PDF %s: %s", path.name, exc)
        return ""

    raw = "\n\n".join(parts)
    cleaned = clean_text(raw)

    if not cleaned.strip():
        logger.warning("No extractable text in %s (likely scanned).", path.name)

    return cleaned


def needs_ocr(text: str, num_pages: int = 1) -> bool:
    """
    Heuristic: does this extracted text look like it came from a scanned PDF?

    A digital resume should yield at least MIN_CHARS_PER_PAGE characters
    per page. Much less than that â†’ almost certainly an image-only PDF.
    """
    if num_pages < 1:
        num_pages = 1
    return len(text.strip()) < (MIN_CHARS_PER_PAGE * num_pages)