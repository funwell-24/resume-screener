"""
PDF parsing layer.

Public API:
    parse_pdf(path) -> str              # main entry point
    clean_text(text) -> str             # normalize extracted text
    needs_ocr(text, num_pages) -> bool  # heuristic for scanned PDFs
    extract_text_with_ocr(path) -> str  # OCR fallback
    is_tesseract_available() -> bool    # is Tesseract installed?

Everything else is internal.
"""

from .pdf_parser import parse_pdf, needs_ocr
from .cleaner import clean_text
from .ocr_fallback import extract_text_with_ocr, is_tesseract_available

__all__ = [
    "parse_pdf",
    "clean_text",
    "needs_ocr",
    "extract_text_with_ocr",
    "is_tesseract_available",
]
