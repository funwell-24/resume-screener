"""
Headless batch runner — no UI, just results.

Runs the full pipeline (parse → extract → score → rank) and prints /
exports the ranked list. Supports:
    - Terminal output (colored table)
    - CSV export
    - JSON export
    - Quiet mode for CI

Examples
--------
    # Basic run
    python scripts/run_cli.py data/job_descriptions/sample_jd.txt data/resumes/

    # Export ranked list to CSV
    python scripts/run_cli.py jd.txt data/resumes/ --csv out.csv

    # JSON + full details
    python scripts/run_cli.py jd.txt data/resumes/ --json out.json --verbose

    # CI-friendly (no banner, exit code = 0 if any processed, 1 if all failed)
    python scripts/run_cli.py jd.txt data/resumes/ --quiet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Importable src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from src.pipeline import parse_job_description_file, run_batch, BatchResult
from src.utils import setup_logging, get_logger, write_json
from src.utils.validators import validate_batch_input, ValidationError

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_ANSI = {
    "bold": "\033[1m",
    "dim": "\033[2m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "blue": "\033[34m",
    "reset": "\033[0m",
}


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _c(text: str, *styles: str) -> str:
    if not _supports_color():
        return text
    prefix = "".join(_ANSI.get(s, "") for s in styles)
    return f"{prefix}{text}{_ANSI['reset']}"


def _score_color(score: float | None) -> str:
    if score is None:
        return "dim"
    if score >= 75:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def print_header(job, result: BatchResult) -> None:
    print()
    print(_c("═" * 72, "dim"))
    print(_c("  AI RESUME SCREENER", "bold"))
    print(_c("═" * 72, "dim"))
    print(f"  Job title:  {_c(job.title or '(untitled)', 'bold')}")
    print(f"  Required:   {len(job.required_skills)} skills")
    if job.required_years is not None:
        print(f"  Experience: {job.required_years:.1f}+ years")
    print(f"  Candidates: {result.n_processed} processed, {result.n_failed} failed")
    print(_c("─" * 72, "dim"))


def print_ranked(result: BatchResult, verbose: bool = False) -> None:
    if result.n_processed == 0:
        print(_c("  No candidates successfully processed.", "red"))
        return

    for rc in result.ranked:
        c = rc.candidate
        s = rc.score
        score_str = (
            f"{s.display_score:5.1f}" if s.display_score is not None else "  —  "
        )
        color = _score_color(s.display_score)
        flag = _c(" ★ REVIEW", "blue", "bold") if s.recommended_for_review else ""

        print(
            f"  {_c(f'#{c.rank:>2}', 'dim')}  "
            f"{_c(c.display_name.ljust(24), 'bold')}  "
            f"{_c(score_str, color, 'bold')}  "
            f"{c.total_years:>4.1f}y  "
            f"{c.education_level.replace('_', ' ').title().ljust(12)}"
            f"{flag}"
        )

        if verbose:
            print(f"       matched: {', '.join(s.matched_skills) or '(none)'}")
            print(f"       missing: {', '.join(s.missing_skills) or '(none)'}")
            print(f"       {s.explanation}")

    print(_c("─" * 72, "dim"))


def print_failures(result: BatchResult) -> None:
    if not result.failures:
        return
    print(_c(f"\n  ⚠ {len(result.failures)} file(s) failed:", "yellow", "bold"))
    for f in result.failures:
        print(f"     • {f['filename']}: {f['error']}")
    print()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

def export_csv(result: BatchResult, path: Path) -> None:
    df = result.to_dataframe()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  ✓ CSV written: {path}")


def export_json(result: BatchResult, path: Path) -> None:
    write_json(path, result.to_dict())
    print(f"  ✓ JSON written: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the resume screening pipeline headlessly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("jd_path", type=Path, help="Path to job description (.txt)")
    parser.add_argument(
        "resume_paths", nargs="+", type=Path,
        help="PDF files and/or directories containing PDFs",
    )
    parser.add_argument("--csv", type=Path, help="Export ranked list to CSV")
    parser.add_argument("--json", type=Path, help="Export full result to JSON")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print matched/missing skills per candidate",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress banner; print only ranked list",
    )
    parser.add_argument(
        "--no-ocr", action="store_true",
        help="Disable OCR fallback (faster, may miss scanned PDFs)",
    )
    args = parser.parse_args()

    # ---- Logging -----------------------------------------------------
    setup_logging("WARNING" if args.quiet else "INFO")

    # ---- JD ----------------------------------------------------------
    if not args.jd_path.exists():
        print(f"❌ JD not found: {args.jd_path}", file=sys.stderr)
        return 2

    try:
        job = parse_job_description_file(args.jd_path)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Could not parse JD: {exc}", file=sys.stderr)
        return 2

    if not job.raw_text:
        print("❌ JD is empty", file=sys.stderr)
        return 2

    # ---- PDFs --------------------------------------------------------
    try:
        pdfs = validate_batch_input(
            list(args.resume_paths),
            max_count=settings.MAX_RESUMES_PER_BATCH,
        )
    except ValidationError as exc:
        print(f"❌ Invalid resume input: {exc}", file=sys.stderr)
        return 2

    if not pdfs:
        print("❌ No valid PDFs found", file=sys.stderr)
        return 2

    # ---- Run ---------------------------------------------------------
    if not args.quiet:
        print(f"\n📄 Processing {len(pdfs)} PDF(s)…")

    try:
        result = run_batch(pdfs, job, allow_ocr=not args.no_ocr)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Batch failed: {exc}", file=sys.stderr)
        logger.exception("Batch runner failed")
        return 1

    # ---- Output ------------------------------------------------------
    if not args.quiet:
        print_header(job, result)

    print_ranked(result, verbose=args.verbose)

    if not args.quiet:
        print_failures(result)

    # ---- Exports -----------------------------------------------------
    if args.csv:
        export_csv(result, args.csv)
    if args.json:
        export_json(result, args.json)

    # ---- Exit code ---------------------------------------------------
    # 0 = success (at least one processed)
    # 1 = complete failure (nothing processed)
    # 2 = input error (already handled above)
    if result.n_processed == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())