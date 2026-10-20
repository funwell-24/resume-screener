"""
Seed data/resumes/ with sample PDFs.

Sources (in priority order):
    1. --from DIR      Copy PDFs from a local directory
    2. --from URLS     Download from URLs listed in a file
    3. (no source)     Create a synthetic placeholder PDF for smoke tests

Also ensures the data/ directory structure exists:
    data/resumes/
    data/job_descriptions/
    data/processed/
    data/labeled/

Examples
--------
    # Seed from a local folder
    python scripts/ingest_sample_resumes.py --from ~/Downloads/sample_resumes

    # Seed from a URLs file
    python scripts/ingest_sample_resumes.py --from-urls urls.txt

    # Create a placeholder for pipeline testing
    python scripts/ingest_sample_resumes.py --placeholder
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from src.utils import setup_logging, get_logger, ensure_dir, safe_filename
from src.utils.validators import validate_pdf, ValidationError

logger = get_logger(__name__)


_SAMPLE_JD = """Senior Python Data Engineer

Required skills: Python, pandas, SQL, AWS, Docker, scikit-learn.
Minimum 3 years of experience building data pipelines.

You will design and maintain ETL pipelines, deploy ML models
to production, and collaborate with data scientists.
"""


def ensure_data_layout() -> None:
    """Create the standard data directory tree."""
    for d in (
        settings.RESUME_DIR,
        settings.JD_DIR,
        settings.PROCESSED_DIR,
        settings.LABELED_DIR,
    ):
        ensure_dir(d)
        print(f"  ✓ {d.relative_to(settings.PROJECT_ROOT)}")


def write_sample_jd() -> Path:
    """Create a default job description if missing."""
    target = settings.JD_DIR / "sample_jd.txt"
    if target.exists():
        print(f"  · {target.relative_to(settings.PROJECT_ROOT)} already exists")
        return target
    target.write_text(_SAMPLE_JD, encoding="utf-8")
    print(f"  ✓ {target.relative_to(settings.PROJECT_ROOT)} (sample JD created)")
    return target


def copy_from_directory(src_dir: Path) -> int:
    """Copy valid PDFs from a directory into data/resumes/."""
    if not src_dir.is_dir():
        logger.error("Not a directory: %s", src_dir)
        return 0

    copied = 0
    for pdf in sorted(src_dir.glob("*.pdf")):
        try:
            validate_pdf(pdf)
        except ValidationError as exc:
            logger.warning("Skipping %s: %s", pdf.name, exc)
            continue

        target = settings.RESUME_DIR / safe_filename(pdf.name)
        if target.exists():
            logger.info("Already present: %s", target.name)
            continue

        shutil.copy2(pdf, target)
        copied += 1
        print(f"  ✓ Copied {pdf.name}")

    return copied


def download_from_urls(urls_file: Path) -> int:
    """Download PDFs listed in a text file (one URL per line)."""
    if not urls_file.exists():
        logger.error("URL list not found: %s", urls_file)
        return 0

    urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    downloaded = 0
    for i, url in enumerate(urls, start=1):
        # Derive filename from URL
        filename = url.rstrip("/").split("/")[-1] or f"sample_{i}.pdf"
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        target = settings.RESUME_DIR / safe_filename(filename)

        if target.exists():
            logger.info("Already present: %s", target.name)
            continue

        try:
            print(f"  ↓ Downloading {url[:60]}…", end="", flush=True)
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read()
            if not data.startswith(b"%PDF-"):
                print(" ✗ (not a PDF)")
                continue
            target.write_bytes(data)
            downloaded += 1
            print(" ✓")
        except Exception as exc:  # noqa: BLE001
            print(f" ✗ ({exc})")

    return downloaded


def create_placeholder_pdf() -> Path:
    """
    Create a minimal single-page PDF with resume-like text.

    Uses only stdlib — the file is a valid PDF 1.4 that PyMuPDF can parse.
    This lets the demo pipeline run end-to-end without needing real files.
    """
    target = settings.RESUME_DIR / "placeholder_resume.pdf"
    if target.exists():
        print(f"  · {target.relative_to(settings.PROJECT_ROOT)} already exists")
        return target

    text_lines = [
        "Sample Candidate",
        "sample.candidate@example.com  |  +1 555 123 4567",
        "",
        "SUMMARY",
        "Python developer with 4 years of experience in data engineering.",
        "",
        "SKILLS",
        "Python, pandas, SQL, Docker, AWS, scikit-learn, git",
        "",
        "EXPERIENCE",
        "Data Engineer, Acme Corp",
        "Jan 2020 - Present",
        "Built ETL pipelines using Python and AWS.",
        "",
        "EDUCATION",
        "BSc Computer Science, Example University, 2019",
    ]

    # Build a minimal valid PDF
    content = "BT /F1 12 Tf 50 750 Td 14 TL\n"
    for line in text_lines:
        # Escape PDF special chars
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content += f"({safe}) Tj T*\n"
    content += "ET"
    content_bytes = content.encode("latin-1")

    objects = []

    def add_obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    # Reserve object 1 for catalog
    objects.append(b"")  # placeholder index 0

    # 1: Catalog
    catalog_num = add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")

    # 2: Pages
    pages_num = add_obj(
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    )

    # 3: Page
    add_obj(
        (
            f"<< /Type /Page /Parent {pages_num} 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 5 0 R >> >> "
            f"/Contents 4 0 R >>"
        ).encode()
    )

    # 4: Content stream
    add_obj(
        f"<< /Length {len(content_bytes)} >>\nstream\n".encode()
        + content_bytes
        + b"\nendstream"
    )

    # 5: Font
    add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    # Fix catalog pointer
    objects[catalog_num - 1] = b"<< /Type /Catalog /Pages 2 0 R >>"

    # Serialize
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for i, body in enumerate(objects[1:], start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode()
        pdf += body + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n".encode()

    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_num} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    target.write_bytes(bytes(pdf))
    print(f"  ✓ {target.relative_to(settings.PROJECT_ROOT)} (placeholder created)")
    return target


def summarize() -> None:
    """Print what's currently in data/resumes/."""
    pdfs = sorted(settings.RESUME_DIR.glob("*.pdf"))
    total_mb = sum(p.stat().st_size for p in pdfs) / (1024 * 1024)
    print(f"\n📂 data/resumes/ → {len(pdfs)} PDF(s), {total_mb:.1f} MB total")
    for p in pdfs[:20]:
        print(f"     • {p.name}")
    if len(pdfs) > 20:
        print(f"     … and {len(pdfs) - 20} more")

    jds = sorted(settings.JD_DIR.glob("*.txt"))
    if jds:
        print(f"\n📂 data/job_descriptions/ → {len(jds)} file(s)")
        for p in jds:
            print(f"     • {p.name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed data/ with sample resumes and a starter JD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--from", dest="from_dir", type=Path,
        help="Copy PDFs from this directory",
    )
    parser.add_argument(
        "--from-urls", dest="from_urls", type=Path,
        help="Download PDFs listed in this file (one URL per line)",
    )
    parser.add_argument(
        "--placeholder", action="store_true",
        help="Create a synthetic placeholder PDF for pipeline testing",
    )
    parser.add_argument(
        "--skip-jd", action="store_true",
        help="Do not create the sample JD",
    )
    args = parser.parse_args()

    setup_logging()

    print("\n📂 Ensuring data layout…")
    ensure_data_layout()

    if not args.skip_jd:
        write_sample_jd()

    created = 0

    if args.from_dir:
        print(f"\n📥 Copying PDFs from {args.from_dir}…")
        created += copy_from_directory(args.from_dir)

    if args.from_urls:
        print(f"\n📥 Downloading PDFs from {args.from_urls}…")
        created += download_from_urls(args.from_urls)

    if args.placeholder or created == 0:
        print("\n🔧 Creating placeholder resume…")
        create_placeholder_pdf()

    summarize()

    print("\n✅ Done. Next: python scripts/run_cli.py "
          "data/job_descriptions/sample_jd.txt data/resumes/\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())