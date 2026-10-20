"""
OCR fallback for scanned / image-only PDFs.

Only used when `pdf_parser.parse_pdf` returns very little text.
Requires Tesseract installed on the system:

    Ubuntu:  sudo apt install tesseract-ocr
    macOS:   brew install tesseract
    Windows: https://github.com/UB-Mannheim/tesseract/wiki

The `pytesseract` Python package is required only if you call this.
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

# Rasterize at ~200â€“300 DPI: enough for OCR, small enough to be fast.
OCR_DPI = 250

# Page images larger than this (px) get downscaled by fitz automatically.
OCR_TIMEOUT_SECONDS = 30


def _import_ocr_stack():
    """
    Import pytesseract lazily so the rest of the package works without it.
    Raises ImportError with a helpful message if missing.
    """
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "OCR requires 'pytesseract' and 'Pillow'. "
            "Install with: pip install pytesseract pillow\n"
            "You also need the Tesseract binary installed on your system."
        ) from exc


def _page_to_image(page: "fitz.Page", dpi: int = OCR_DPI):
    """Rasterize a PDF page to a PIL Image at the given DPI."""
    from PIL import Image
    import io

    zoom = dpi / 72.0  # fitz default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def extract_text_with_ocr(path: str | Path, dpi: int = OCR_DPI) -> str:
    """
    Run OCR on every page of a PDF and return cleaned text.

    Parameters
    ----------
    path : str | Path
        PDF file path.
    dpi : int
        Rasterization DPI. 250 is a good balance of accuracy vs. speed.

    Returns
    -------
    str
        Cleaned OCR text. Empty string if OCR yields nothing.
    """
    _import_ocr_stack()
    import pytesseract

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    parts: list[str] = []

    with fitz.open(path) as doc:
        for page_num, page in enumerate(doc, start=1):
            try:
                image = _page_to_image(page, dpi=dpi)
                # --psm 3 = "fully automatic" page layout analysis.
                # Good default for resumes (blocks + columns).
                page_text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                    config=f"--psm 3 --oem 3",
                    timeout=OCR_TIMEOUT_SECONDS,
                )
                if page_text.strip():
                    parts.append(page_text)
            except RuntimeError as exc:
                # pytesseract.timeout raises RuntimeError
                logger.warning(
                    "OCR timeout on page %d of %s: %s", page_num, path.name, exc
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OCR failed on page %d of %s: %s", page_num, path.name, exc
                )
                continue

    return clean_text("\n\n".join(parts))


def is_tesseract_available() -> bool:
    """
    Utility: return True if Tesseract is installed and reachable.

    The UI can call this once at startup and hide the "OCR" toggle if False.
    """
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001
        return False