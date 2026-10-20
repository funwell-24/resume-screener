"""
Text normalization for extracted PDF content.

Pipeline (order matters):
    1. Unicode normalization (NFKC) — collapse look-alike characters
    2. Fix hyphenated line breaks ("python-\nscript" → "pythonscript"? no —
       we join only when safe: "develop-\nment" → "development")
    3. Remove repeated page headers/footers (page numbers, "Page X of Y")
    4. Normalize whitespace (bullets, tabs, NBSP, multiple blanks)
    5. Strip control characters (keep \n)

Every step is deterministic and cheap. No NLP here — that's in extraction/.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# ---------------------------------------------------------------------------
# Regexes compiled once at import — reused every call.
# ---------------------------------------------------------------------------

# Hyphen followed by newline, then a lowercase letter — likely a soft break.
# We only join when the next char is lowercase, to avoid mangling "COVID-\n19".
_SOFT_HYPHEN_BREAK = re.compile(r"([a-zA-Z])-\s*\n\s*([a-z])")

# Common footer/header patterns that repeat on every page.
_PAGE_NUMBER_PATTERNS = [
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
    re.compile(r"^\s*-\s*\d+\s*-\s*$"),
    re.compile(r"^\s*\d+\s*$"),
]

# Bullet glyphs → "- "
_BULLETS = re.compile(r"^[\s]*[•●○◦▪▫■□‣⁃∙·\u2022\u2023\u2043\u2219]\s*", re.MULTILINE)

# Multi-whitespace → single space (but NOT newlines)
_MULTI_SPACE = re.compile(r"[ \t\u00A0\u2007\u202F]+")

# More than 2 consecutive newlines → exactly 2 (paragraph break)
_MULTI_NEWLINE = re.compile(r"\n{3,}")

# Control chars (except \n and \t)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _normalize_unicode(text: str) -> str:
    """NFKC handles ligatures (ﬁ→fi), full-width chars, etc."""
    text = unicodedata.normalize("NFKC", text)
    # Smart quotes → straight quotes (safer for regex downstream)
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201C", '"').replace("\u201D", '"')
    # En-dash / em-dash → hyphen (date ranges like "2019–2022")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    return text


def _fix_soft_hyphens(text: str) -> str:
    """Join 'develop-\\nment' → 'development' but keep 'COVID-\\n19' intact."""
    return _SOFT_HYPHEN_BREAK.sub(r"\1\2", text)


def _remove_repeated_lines(text: str) -> str:
    """
    Drop lines that appear identically 3+ times (page headers/footers).

    Resumes are 1–3 pages, so anything appearing 3+ times is almost
    certainly boilerplate. Rare content (skill names, job titles) won't
    repeat enough to be dropped.
    """
    lines = text.split("\n")
    stripped = [ln.strip() for ln in lines]
    counts = Counter(ln for ln in stripped if len(ln) > 2)
    boilerplate = {ln for ln, c in counts.items() if c >= 3}

    if not boilerplate:
        return text

    return "\n".join(ln for ln, s in zip(lines, stripped) if s not in boilerplate)


def _strip_page_numbers(text: str) -> str:
    """Remove stand-alone page number lines ('Page 2 of 5', '- 3 -', '2')."""
    out_lines = []
    for line in text.split("\n"):
        if any(p.match(line) for p in _PAGE_NUMBER_PATTERNS):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _normalize_whitespace(text: str) -> str:
    text = _MULTI_SPACE.sub(" ", text)
    # Collapse spaces around newlines
    text = re.sub(r" *\n *", "\n", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    """
    Full normalization pipeline. Idempotent — safe to run twice.

    Use this on every raw PDF extraction before passing to extraction/.
    """
    if not text:
        return ""

    text = _CONTROL_CHARS.sub("", text)
    text = _normalize_unicode(text)
    text = _fix_soft_hyphens(text)
    text = _remove_repeated_lines(text)
    text = _strip_page_numbers(text)
    text = _BULLETS.sub("- ", text)
    text = _normalize_whitespace(text)

    return text