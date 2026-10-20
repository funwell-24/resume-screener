"""
Experience extraction: parse date ranges → total years worked.

Handles common formats:
    Jan 2019 – Mar 2022
    2019-2022
    03/2019 - 06/2022
    March 2019 to Present
    2019 – present
    Summer 2020
    Sep 2018 – current

Returns:
    - total_years: sum of non-overlapping intervals (current job → today)
    - entries: list of (start, end, raw_text, title_hint)
    - n_jobs: count of intervals detected
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_PRESENT_WORDS = r"(?:present|current|now|today|ongoing|to\s*date)"

# Month name (optional) + year, OR month/year, OR just year
_MONTH_YEAR = (
    r"(?P<{prefix}month>[A-Za-z]{{3,9}})?[\s.,/-]*"
    r"(?P<{prefix}year>(?:19|20)\d{{2}})"
)

_DATE_RANGE = re.compile(
    r"(?P<start>" + _MONTH_YEAR.format(prefix="s_") + r")"
    r"\s*(?:-|–|—|to|until|through)\s*"
    r"(?P<end>" + _MONTH_YEAR.format(prefix="e_") + r"|" + _PRESENT_WORDS + r")",
    re.IGNORECASE,
)


@dataclass
class ExperienceEntry:
    start: date | None = None
    end: date | None = None
    raw_text: str = ""
    title_hint: str = ""

    def duration_years(self, today: date | None = None) -> float:
        if not self.start:
            return 0.0
        end = self.end or (today or date.today())
        days = (end - self.start).days
        return max(0.0, days / 365.25)


@dataclass
class ExperienceInfo:
    total_years: float = 0.0
    entries: list[ExperienceEntry] = field(default_factory=list)

    @property
    def n_jobs(self) -> int:
        return len(self.entries)


def _parse_month(name: str | None) -> int | None:
    if not name:
        return None
    key = name.strip().lower()[:4]
    # Try 3-letter then full
    for length in (3, 4, len(key)):
        if key[:length] in _MONTHS:
            return _MONTHS[key[:length]]
    return None


def _parse_date(month_str: str | None, year_str: str | None, is_end: bool) -> date | None:
    if not year_str:
        return None
    try:
        year = int(year_str)
    except ValueError:
        return None

    month = _parse_month(month_str)
    if month is None:
        # No month → assume start=Jan, end=Dec (conservative expansion)
        month = 1 if not is_end else 12

    # Guard month/year
    if not (1 <= month <= 12):
        month = 1
    if not (1950 <= year <= 2100):
        return None

    # Use day=1 for both start and end; duration calculation is approximate
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def _title_hint_from_context(text: str, match_start: int, window: int = 120) -> str:
    """
    Best-effort job title guess: the last non-empty line before the date range.
    """
    lo = max(0, match_start - window)
    preceding = text[lo:match_start]
    lines = [ln.strip() for ln in preceding.split("\n") if ln.strip()]
    if not lines:
        return ""
    last = lines[-1]
    # Titles are short and don't end with a period
    if len(last) <= 80 and not last.endswith("."):
        return last
    return ""


def _merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Merge overlapping date intervals."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def extract_experience(
    text: str,
    today: date | None = None,
    default_present_end: date | None = None,
) -> ExperienceInfo:
    """
    Extract experience entries and compute total (non-overlapping) years.
    """
    info = ExperienceInfo()
    if not text or not text.strip():
        return info

    today = today or date.today()
    present_end = default_present_end or today

    raw_intervals: list[tuple[date, date]] = []

    for match in _DATE_RANGE.finditer(text):
        start = _parse_date(match.group("s_month"), match.group("s_year"), is_end=False)
        if not start:
            continue

        end_raw = match.group("end")
        if end_raw and re.fullmatch(_PRESENT_WORDS, end_raw, re.IGNORECASE):
            end = present_end
        else:
            end = _parse_date(match.group("e_month"), match.group("e_year"), is_end=True)

        if not end or end < start:
            continue

        entry = ExperienceEntry(
            start=start,
            end=end,
            raw_text=match.group(0),
            title_hint=_title_hint_from_context(text, match.start()),
        )
        info.entries.append(entry)
        raw_intervals.append((start, end))

    merged = _merge_intervals(raw_intervals)
    total_days = sum((end - start).days for start, end in merged)
    info.total_years = round(max(0.0, total_days / 365.25), 2)

    return info


def required_years_from_jd(jd_text: str) -> float | None:
    """
    Look for phrases like "3+ years", "at least 5 years", "minimum 2 years".
    Returns None if no requirement is stated.
    """
    patterns = [
        re.compile(r"(\d+)\s*\+\s*(?:years?|yrs?)", re.IGNORECASE),
        re.compile(r"(?:at\s+least|minimum(?:\s+of)?|min\.?)\s*(\d+)\s*(?:years?|yrs?)", re.IGNORECASE),
        re.compile(r"(\d+)\s*(?:-|–|to)\s*\d+\s*(?:years?|yrs?)", re.IGNORECASE),
        re.compile(r"(\d+)\s*(?:years?|yrs?)\s+(?:of\s+)?experience", re.IGNORECASE),
    ]
    best: float | None = None
    for pat in patterns:
        for m in pat.finditer(jd_text):
            try:
                yrs = float(m.group(1))
            except (ValueError, IndexError):
                continue
            if yrs > 40:  # obviously wrong
                continue
            if best is None or yrs > best:
                best = yrs
    return best