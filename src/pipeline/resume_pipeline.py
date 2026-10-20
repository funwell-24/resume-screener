"""
Single-resume pipeline: PDF → parsed text → extraction → scored Candidate.

Public API:
    process_resume(pdf_path, job) -> ProcessedResume

Design:
    - Pure orchestration. All heavy lifting is delegated to
      parsing/ and extraction/.
    - Never raises on bad input — returns a ProcessedResume with
      `error` set. The batch runner uses this to report failures
      without killing the whole batch.
    - Caches parse results to data/processed/ if enabled in settings.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from config import settings
from src.parsing import parse_pdf
from src.parsing.ocr_fallback import extract_text_with_ocr, is_tesseract_available
from src.parsing.pdf_parser import needs_ocr
from src.extraction import (
    split_sections,
    extract_skills,
    extract_contact,
    extract_education,
    extract_experience,
    ResumeSections,
    ContactInfo,
    EducationInfo,
    ExperienceInfo,
)
from .jd_parser import JobRequirements

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ProcessedResume
# ---------------------------------------------------------------------------

@dataclass
class ProcessedResume:
    """All the information we extracted from one resume PDF."""

    # Identity
    filename: str
    file_path: str

    # Parsed content
    raw_text: str = ""
    sections: ResumeSections | None = None

    # Extraction results
    skills: set[str] = field(default_factory=set)
    contact: ContactInfo | None = None
    education: EducationInfo | None = None
    experience: ExperienceInfo | None = None

    # Diagnostics
    num_pages: int = 0
    used_ocr: bool = False
    error: str | None = None

    # ---- Properties -------------------------------------------------

    @property
    def candidate_id(self) -> str:
        """Stable key for this resume (used in batch results dicts)."""
        return self.file_path

    @property
    def display_name(self) -> str:
        """Best human-readable name for the candidate."""
        if self.contact and self.contact.name:
            return self.contact.name
        return Path(self.filename).stem

    @property
    def total_years(self) -> float:
        if self.experience:
            return self.experience.total_years
        return 0.0

    # ---- Serialization / conversion ---------------------------------

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "file_path": self.file_path,
            "display_name": self.display_name,
            "skills": sorted(self.skills),
            "email": (self.contact.email if self.contact else ""),
            "phone": (self.contact.phone if self.contact else ""),
            "linkedin": (self.contact.linkedin if self.contact else ""),
            "github": (self.contact.github if self.contact else ""),
            "education_level": (
                self.education.highest_level if self.education else "unknown"
            ),
            "education_institution": (
                self.education.entries[0].institution
                if self.education and self.education.entries
                else ""
            ),
            "total_years": self.total_years,
            "num_pages": self.num_pages,
            "used_ocr": self.used_ocr,
            "error": self.error,
        }

    def to_candidate(self) -> "Candidate":
        """Convert to the JSON-safe display record."""
        # Import locally to avoid circular imports at module load
        from src.models import Candidate

        return Candidate(
            filename=self.filename,
            file_path=self.file_path,
            name=(self.contact.name if self.contact else ""),
            email=(self.contact.email if self.contact else ""),
            phone=(self.contact.phone if self.contact else ""),
            linkedin=(self.contact.linkedin if self.contact else ""),
            github=(self.contact.github if self.contact else ""),
            website=(self.contact.website if self.contact else ""),
            skills=sorted(self.skills),
            total_years=self.total_years,
            n_jobs=(self.experience.n_jobs if self.experience else 0),
            education_level=(
                self.education.highest_level if self.education else "unknown"
            ),
            education_institution=(
                self.education.entries[0].institution
                if self.education and self.education.entries else ""
            ),
            education_field=(
                self.education.fields[0]
                if self.education and self.education.fields else ""
            ),
            num_pages=self.num_pages,
            used_ocr=self.used_ocr,
            error=self.error,
        )


# ---------------------------------------------------------------------------
# Parse caching
# ---------------------------------------------------------------------------

def _file_hash(path: Path) -> str:
    """Hash file contents (not path) so renames don't invalidate the cache."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _cache_path(path: Path) -> Path:
    return settings.PROCESSED_DIR / f"{_file_hash(path)}.txt"


def _read_cache(path: Path) -> str | None:
    if not settings.PARSE_CACHE_ENABLED:
        return None
    cp = _cache_path(path)
    if cp.exists():
        try:
            return cp.read_text(encoding="utf-8-sig")
        except OSError:
            return None
    return None


def _write_cache(path: Path, text: str) -> None:
    if not settings.PARSE_CACHE_ENABLED:
        return
    try:
        settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(path).write_text(text, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cache write failed for %s: %s", path.name, exc)


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------

def process_resume(
    pdf_path: str | Path,
    job: JobRequirements,  # accepted for future use (e.g., skill-aware OCR)
    *,
    allow_ocr: bool = True,
) -> ProcessedResume:
    """
    Run the full extraction pipeline on one resume PDF.

    Never raises — failures are captured in `result.error` so the batch
    runner can report them cleanly.

    Parameters
    ----------
    pdf_path : str | Path
    job : JobRequirements
        The parsed JD. Currently unused inside, but kept in the signature
        so future JD-aware extraction (e.g., "only extract skills relevant
        to this JD") can be added without a breaking change.
    allow_ocr : bool
        If True and the PDF looks scanned, try Tesseract fallback.
    """
    pdf_path = Path(pdf_path)

    result = ProcessedResume(
        filename=pdf_path.name,
        file_path=str(pdf_path),
    )

    if not pdf_path.exists():
        result.error = f"File not found: {pdf_path}"
        return result

    # ---- Step 1: text extraction (with cache) ------------------------
    try:
        try:
            import pymupdf as fitz  # PyMuPDF >= 1.24
        except ImportError:
            import fitz
        with fitz.open(pdf_path) as doc:
            result.num_pages = len(doc)
    except Exception as exc:  # noqa: BLE001
        result.error = f"Cannot open PDF: {exc}"
        return result

    text = _read_cache(pdf_path)
    if text is None:
        try:
            text = parse_pdf(pdf_path)
        except Exception as exc:  # noqa: BLE001
            result.error = f"Parse failed: {exc}"
            return result

        # OCR fallback for scanned PDFs
        if allow_ocr and needs_ocr(text, result.num_pages):
            if is_tesseract_available():
                logger.info("OCR fallback triggered for %s", pdf_path.name)
                try:
                    ocr_text = extract_text_with_ocr(pdf_path)
                    if len(ocr_text) > len(text):
                        text = ocr_text
                        result.used_ocr = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning("OCR failed for %s: %s", pdf_path.name, exc)
            else:
                logger.info(
                    "Scanned PDF detected but Tesseract not installed: %s",
                    pdf_path.name,
                )

        _write_cache(pdf_path, text)

    result.raw_text = text

    if not text.strip():
        result.error = "No extractable text (scanned PDF and OCR unavailable)"
        return result

    # ---- Step 2: sectioning ------------------------------------------
    try:
        result.sections = split_sections(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sectioning failed for %s: %s", pdf_path.name, exc)
        result.sections = ResumeSections(header=text)

    # ---- Step 3: structured extraction -------------------------------
    try:
        result.contact = extract_contact(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Contact extraction failed for %s: %s", pdf_path.name, exc)

    # Skills — full text is fine, but scope to sections when possible
    try:
        result.skills = extract_skills(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skill extraction failed for %s: %s", pdf_path.name, exc)
        result.skills = set()

    # Education — prefer scoped section, fall back to full text
    try:
        edu_text = (
            result.sections.education
            if result.sections and result.sections.education
            else text
        )
        result.education = extract_education(edu_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Education extraction failed for %s: %s", pdf_path.name, exc)

    # Experience — prefer scoped section, fall back to full text
    try:
        exp_text = (
            result.sections.experience
            if result.sections and result.sections.experience
            else text
        )
        result.experience = extract_experience(exp_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Experience extraction failed for %s: %s", pdf_path.name, exc)

    return result