"""
Input validation — fail fast with helpful errors.

Where these are used:
    - `validate_pdf(path)` before calling parse_pdf — catches wrong
      extension, wrong magic bytes, oversized files.
    - `validate_file_size(path)` separately, so the UI can show a
      size-limit message without opening the file.
    - `validate_batch_input(paths)` in batch_runner — normalizes a mixed
      list of files and directories into a clean PDF list.
    - `validate_jd_text(text)` before parsing — catches empty / too-short.

Every validator raises `ValidationError` with a human-readable message
that the UI or CLI can display directly to the user.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised for user-facing input validation failures."""


# PDF files always start with these bytes
_PDF_MAGIC = b"%PDF-"

# Reasonable upper limit for resume PDFs
MAX_PDF_SIZE_MB = 25
MIN_JD_CHARS = 30
MAX_JD_CHARS = 100_000


# ---------------------------------------------------------------------------
# PDF validation
# ---------------------------------------------------------------------------

def validate_file_size(
    path: str | Path,
    max_mb: float = MAX_PDF_SIZE_MB,
) -> int:
    """
    Check that a file exists and is under the size limit.

    Returns the file size in bytes. Raises ValidationError otherwise.
    """
    p = Path(path)
    if not p.exists():
        raise ValidationError(f"File not found: {p}")
    if not p.is_file():
        raise ValidationError(f"Not a regular file: {p}")

    size = p.stat().st_size
    size_mb = size / (1024 * 1024)
    if size_mb > max_mb:
        raise ValidationError(
            f"File too large: {p.name} is {size_mb:.1f} MB "
            f"(limit: {max_mb} MB)"
        )
    if size == 0:
        raise ValidationError(f"File is empty: {p.name}")
    return size


def validate_pdf(path: str | Path) -> Path:
    """
    Validate that a path points to a genuine PDF file.

    Checks:
        - Exists and is a regular file
        - .pdf extension (case-insensitive)
        - Under size limit
        - Starts with %PDF- magic bytes (catches renamed .docx)

    Returns the resolved Path. Raises ValidationError otherwise.
    """
    p = Path(path)
    if p.suffix.lower() != ".pdf":
        raise ValidationError(
            f"Not a PDF file: {p.name} (expected .pdf extension)"
        )

    validate_file_size(p)

    # Magic byte check
    try:
        with p.open("rb") as f:
            header = f.read(8)
    except OSError as exc:
        raise ValidationError(f"Cannot read {p.name}: {exc}") from exc

    if not header.startswith(_PDF_MAGIC):
        raise ValidationError(
            f"File is not a valid PDF (missing %PDF- header): {p.name}"
        )

    return p.resolve()


def validate_batch_input(
    paths: list[str | Path],
    *,
    max_count: int = 200,
    strict: bool = False,
) -> list[Path]:
    """
    Normalize a mixed list of file/directory paths into a PDF path list.

    Parameters
    ----------
    paths : list[str | Path]
        Mix of files, directories, and possibly invalid entries.
    max_count : int
        Reject if total valid PDFs exceed this count.
    strict : bool
        If True, any invalid path raises ValidationError.
        If False, invalid paths are logged and skipped.

    Returns
    -------
    list[Path]
        Deduplicated, order-preserved list of validated PDF paths.
    """
    if not paths:
        raise ValidationError("No input paths provided")

    collected: list[Path] = []
    errors: list[str] = []

    for raw in paths:
        p = Path(raw)

        if not p.exists():
            msg = f"Path does not exist: {p}"
            if strict:
                raise ValidationError(msg)
            errors.append(msg)
            continue

        if p.is_dir():
            pdfs = sorted(p.glob("*.pdf"))
            if not pdfs:
                msg = f"No PDFs found in directory: {p}"
                if strict:
                    raise ValidationError(msg)
                errors.append(msg)
                continue
            for pdf in pdfs:
                try:
                    collected.append(validate_pdf(pdf))
                except ValidationError as exc:
                    if strict:
                        raise
                    errors.append(str(exc))
            continue

        try:
            collected.append(validate_pdf(p))
        except ValidationError as exc:
            if strict:
                raise
            errors.append(str(exc))

    # Deduplicate, preserve order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in collected:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if not unique:
        raise ValidationError(
            "No valid PDF files found. "
            + (f"Errors: {errors[:3]}" if errors else "")
        )

    if len(unique) > max_count:
        raise ValidationError(
            f"Too many PDFs: {len(unique)} > {max_count}. Split into smaller batches."
        )

    if errors:
        logger.warning(
            "Skipped %d invalid input(s): %s",
            len(errors),
            "; ".join(errors[:3]) + ("..." if len(errors) > 3 else ""),
        )

    return unique


# ---------------------------------------------------------------------------
# JD validation
# ---------------------------------------------------------------------------

def validate_jd_text(text: str) -> str:
    """
    Validate a job description string.

    Returns the stripped text. Raises ValidationError for empty or
    suspiciously short input — a JD like "python dev" won't yield useful
    requirements anyway.
    """
    if not text or not text.strip():
        raise ValidationError("Job description is empty")

    stripped = text.strip()

    if len(stripped) < MIN_JD_CHARS:
        raise ValidationError(
            f"Job description too short ({len(stripped)} chars, "
            f"minimum {MIN_JD_CHARS}). Add more detail."
        )

    if len(stripped) > MAX_JD_CHARS:
        raise ValidationError(
            f"Job description too long ({len(stripped)} chars, "
            f"maximum {MAX_JD_CHARS})"
        )

    return stripped