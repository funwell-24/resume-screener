"""
Contact information extraction.

Deliberately regex-only — spaCy NER is overkill for email/URLs and
occasionally wrong. Regex with careful patterns is more reliable here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Loose international-ish phone pattern. Accepts: +1 555-123-4567,
# (555) 123-4567, +44 20 7946 0958, 555.123.4567
_PHONE = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s.\-]?)?"          # optional country code
    r"(?:\(?\d{2,4}\)?[\s.\-]?)?"              # optional area code
    r"\d{3,4}[\s.\-]?\d{3,4}"                  # main number groups
)

# LinkedIn: linkedin.com/in/username (with or without protocol)
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9\-_%]+/?",
    re.IGNORECASE,
)

# GitHub
_GITHUB = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9\-_]+/?",
    re.IGNORECASE,
)

# Generic personal website (limited — must look like a URL or www.)
_WEBSITE = re.compile(
    r"(?:https?://)?(?:www\.)[A-Za-z0-9\-]+\.[A-Za-z]{2,}(?:/[^\s]*)?",
    re.IGNORECASE,
)

# Name heuristic: first non-empty line, short, mostly alphabetic.
_NAME_LINE = re.compile(r"^[A-Za-z][A-Za-z.'\- ]{1,60}$")


@dataclass
class ContactInfo:
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    all_emails: list[str] = field(default_factory=list)


def _first_name_line(text: str) -> str:
    """
    Guess the candidate's name from the top of the resume.

    Heuristic: scan the first ~5 non-empty lines, return the first that
    looks like a person's name (alphabetic, 2–5 words, no digits/@/URL).
    """
    for line in text.split("\n")[:8]:
        s = line.strip()
        if not s or len(s) > 60:
            continue
        if "@" in s or "http" in s.lower() or "www." in s.lower():
            continue
        if any(ch.isdigit() for ch in s):
            continue
        if not _NAME_LINE.match(s):
            continue
        words = s.split()
        if 1 <= len(words) <= 5 and all(w[0].isupper() for w in words if w):
            return s
    return ""


def _clean_phone(raw: str) -> str:
    """Strip whitespace, keep only digits/+ and one separator style."""
    return re.sub(r"[^\d+]", "", raw)


def extract_contact(text: str) -> ContactInfo:
    """
    Pull contact details out of cleaned resume text.
    """
    info = ContactInfo()

    # Email (may be multiple)
    emails = [e.lower() for e in _EMAIL.findall(text)]
    if emails:
        info.all_emails = list(dict.fromkeys(emails))
        info.email = info.all_emails[0]

    # Phone — filter out likely false positives (too short / too long)
    for match in _PHONE.finditer(text):
        cleaned = _clean_phone(match.group())
        if 7 <= len(cleaned) <= 15:
            info.phone = match.group().strip()
            break

    # LinkedIn
    li = _LINKEDIN.search(text)
    if li:
        url = li.group().rstrip("/")
        if not url.lower().startswith("http"):
            url = "https://" + url.lstrip("/")
        info.linkedin = url

    # GitHub
    gh = _GITHUB.search(text)
    if gh:
        url = gh.group().rstrip("/")
        if not url.lower().startswith("http"):
            url = "https://" + url.lstrip("/")
        info.github = url

    # Website — only if it isn't linkedin/github
    for match in _WEBSITE.finditer(text):
        u = match.group().lower()
        if "linkedin.com" in u or "github.com" in u:
            continue
        info.website = match.group()
        break

    # Name
    info.name = _first_name_line(text)

    return info