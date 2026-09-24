"""Seed job-discovery filters from the active resume (3.3).

Structural, offline extraction only: experience dates -> seniority band, latest
title -> keyword, skill groups -> terms. Resume text is never expanded through
a model; entries without a usable interval contribute nothing (contract 31).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from app.data import KEY_DISCOVERY_FILTERS
from app.data.models import SectionKind, utcnow
from app.data.repositories import ResumeRepo, SettingsRepo
from app.discovery.services.filters import load_filters, parse_filters
from app.discovery.services.vocab import Seniority

SENIORITY_BANDS: tuple[tuple[int, int | None, str], ...] = (
    (0, 2, Seniority.ENTRY),
    (3, 5, Seniority.MID),
    (6, 9, Seniority.SENIOR),
    (10, None, Seniority.LEAD),
)

# "Jan 2020"/"January 2020"/"2020"; year-only anchors to January (see `_month`).
_MONTH_YEAR_RE = re.compile(r"(?P<month>[A-Za-z]{3,9})?\.?\s*(?P<year>\d{4})")
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_OPEN_END = frozenset({"present", "current"})


def _text(value: object) -> str:
    """Stored scalar as stripped text; uncertainty markers unwrap, uncertain ones read empty."""
    if value is None:
        return ""

    if isinstance(value, dict):
        if value["uncertain"]:
            return ""

        return _text(value["v"])

    return str(value).strip()


def _month(value: str) -> int | None:
    """'Jan 2020' / '2020' -> absolute month index (year * 12 + 0-based month); None if unparseable."""
    match = _MONTH_YEAR_RE.search(value)

    if match is None:
        return None

    month = 1
    token = match.group("month")

    if token:
        month = _MONTHS.get(token[:3].casefold())

        if month is None:
            return None

    return int(match.group("year")) * 12 + (month - 1)


def _now_month() -> int:
    """Current month index from `utcnow()`; tests monkeypatch this module's `utcnow`."""
    now = utcnow()

    return now.year * 12 + (now.month - 1)


def _interval(entry: Mapping) -> tuple[int, int] | None:
    """Entry's covered months [start, end] inclusive; None when the dates are unusable."""
    start = _month(_text(entry.get("start")))

    if start is None:
        return None

    end_text = _text(entry.get("end")).casefold()
    end = _now_month() if end_text in _OPEN_END else _month(end_text)

    if end is None or end < start:
        return None

    return start, end


def _experience_years(entries: Iterable[Mapping]) -> int | None:
    """Union of all usable intervals, whole years; None when nothing is usable."""
    intervals = sorted(interval for interval in (_interval(e) for e in entries) if interval)

    if not intervals:
        return None

    # Overlaps counted once, gaps excluded: merge by start, then sum covered months.
    merged: list[list[int]] = []

    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    months = sum(end - start + 1 for start, end in merged)

    return months // 12


def _latest_title(entries: Iterable[Mapping]) -> str:
    """Title of the most recent dated entry; '' when none has a usable date or title.

    Key is (start or end, end or 0): an entry dated only by its end sorts by
    that end; ties keep the earliest-listed entry. An open "Present" end has no
    parseable month here, so its second component is 0.
    """
    best_key: tuple[int, int] | None = None
    best = ""

    for entry in entries:
        start = _month(_text(entry.get("start")))
        end = _month(_text(entry.get("end")))

        if start is None and end is None:
            continue

        title = _text(entry.get("title"))

        if not title:
            continue

        key = (start or end, end or 0)

        if best_key is None or key > best_key:
            best_key = key
            best = title

    return best


def seniority_band(years: int) -> str:
    """Band whose inclusive year range contains `years`; last band is open-ended."""
    for low, high, band in SENIORITY_BANDS:
        if years >= low and (high is None or years <= high):
            return str(band)

    return ""


def _flat_skills(sections: Iterable[object]) -> list[str]:
    """Skill scalars across SKILLS sections, in order; blanks/uncertain markers dropped."""
    out: list[str] = []

    for section in sections:
        if getattr(section, "kind", None) != SectionKind.SKILLS:
            continue

        content = getattr(section, "content", None)

        if not isinstance(content, list):
            continue

        for entry in content:
            skills = entry.get("skills") if isinstance(entry, dict) else None

            if not isinstance(skills, list):
                continue

            for item in skills:
                text = _text(item)

                if text:
                    out.append(text)

    return out


def seed_from_sections(sections: Iterable[object]) -> dict:
    """Deterministic filter seeds from resume sections; a full validated filter block.

    Only title/seniority/terms are seeded: the resume has no source for the rest
    (decision 3 keeps years_experience dormant). parse_filters validates enum
    spellings and dedupes, so the return is always a complete 9-key block.
    """
    entries: list[Mapping] = []
    skill_sections: list[object] = []

    for section in sections:
        kind = getattr(section, "kind", None)

        if kind == SectionKind.EXPERIENCE:
            content = getattr(section, "content", None)

            if isinstance(content, list):
                entries.extend(e for e in content if isinstance(e, dict))
        elif kind == SectionKind.SKILLS:
            skill_sections.append(section)

    years = _experience_years(entries)

    return parse_filters(
        {
            "title": _latest_title(entries),
            "seniority": [seniority_band(years)] if years is not None else [],
            "terms": _flat_skills(skill_sections),
        }
    )


def seed_filters() -> dict:
    """Seeds from the active resume; DEFAULT_FILTERS shape when no resume is active."""
    resume = ResumeRepo().get_active()

    if resume is None:
        return parse_filters({})

    return seed_from_sections(ResumeRepo().sections(resume.id))


def prefill_filters() -> dict:
    """Persisted block when filters were ever saved, else the active resume's seeds.

    The raw setting is checked, not `load_filters()` — that accessor falls back
    to DEFAULT_FILTERS and would mask "never persisted".
    """
    if SettingsRepo().get(KEY_DISCOVERY_FILTERS):
        return load_filters()

    return seed_filters()
