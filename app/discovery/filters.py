"""Discovery filter block: strict parse, persistence, and the repo query spec."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import timedelta
from enum import StrEnum

from app.data import DEFAULT_FILTERS, KEY_DISCOVERY_FILTERS, utcnow
from app.data.repositories import SettingsRepo, normalize
from app.discovery.errors import FilterError
from app.discovery.vocab import EmploymentType, Seniority, WorkArrangement


class DatePosted(StrEnum):
    """Date-posted window; ANY imposes no bound (handoff decision 4)."""

    ANY = ""
    DAY = "24h"
    WEEK = "7d"
    MONTH = "30d"


# Lookback days per window; keyed by window value, so a persisted string looks
# up directly (StrEnum members hash as their string values). "" -> no bound.
DATE_POSTED_DAYS: dict[str, int] = {
    DatePosted.DAY: 1,
    DatePosted.WEEK: 7,
    DatePosted.MONTH: 30,
}

# Static synonym groups for skill terms (handoff decision 2). Spellings must be
# unambiguous alone: groups whose spellings are substrings of each other
# (postgres/postgresql) add nothing to a LIKE match, and short tokens (ml, js,
# ai, go) false-positive inside unrelated words (HTML, yml, agile).
_SKILL_GROUPS: tuple[tuple[str, ...], ...] = (
    ("aws", "amazon web services"),
    ("gcp", "google cloud", "google cloud platform"),
    ("k8s", "kubernetes"),
)

# Normalized spelling -> its group; an unlisted term matches verbatim.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    normalize(spelling): group for group in _SKILL_GROUPS for spelling in group
}


def _values(key: str, raw: object) -> list[str]:
    """Raw filter value as a list of strings. Query params arrive multi-valued."""
    if raw is None:
        return []

    if isinstance(raw, str):
        return [raw]

    if isinstance(raw, Sequence) and all(isinstance(v, str) for v in raw):
        return list(raw)

    raise FilterError(f"filter '{key}' must be a string or a list of strings, got {raw!r}")


def _single(key: str, values: list[str]) -> str:
    """A scalar filter entry: at most one value, whitespace-stripped."""
    if len(values) > 1:
        raise FilterError(f"filter '{key}' accepts a single value, got {len(values)}")

    return values[0].strip() if values else ""


def _unique(values: list[str]) -> list[str]:
    """Trim, drop blanks, dedupe case-insensitively; first spelling wins."""
    seen: set[str] = set()
    out: list[str] = []

    for value in values:
        text = value.strip()

        if not text or normalize(text) in seen:
            continue

        seen.add(normalize(text))
        out.append(text)

    return out


def _options(enum_cls: type[StrEnum]) -> str:
    return str(sorted(member.value for member in enum_cls))


def _member(key: str, enum_cls: type[StrEnum], values: list[str]) -> str:
    """Strict single-value enum: "" is a member of DatePosted, so it is accepted."""
    text = _single(key, values)

    try:
        return enum_cls(text).value
    except ValueError as exc:
        raise FilterError(
            f"filter '{key}' must be one of {_options(enum_cls)}, got '{text}'"
        ) from exc


def _members(key: str, enum_cls: type[StrEnum], values: list[str]) -> list[str]:
    """Multi-value enum: fold known spellings, reject everything else.

    Blanks are absent, not errors (WorkArrangement.canonical("  ") -> None).
    """
    known = {member.value for member in enum_cls}
    out: list[str] = []

    for value in values:
        canonical = enum_cls.canonical(value)

        if canonical is None:
            continue

        text = str(canonical)

        if text not in known:
            raise FilterError(f"filter '{key}' must be one of {_options(enum_cls)}, got '{value}'")

        if text not in out:
            out.append(text)

    return out


def parse_filters(raw: Mapping[str, object]) -> dict:
    """Strict parse of a raw filter block; unknown key or bad value raises FilterError.

    Accepts query params (multi-valued, so a scalar key is a 1-element list) and
    a JSON body (bare scalars). The result always carries all 9 DEFAULT_FILTERS
    keys; an empty value means "no restriction".
    """
    unknown = sorted(set(raw) - set(DEFAULT_FILTERS))

    if unknown:
        raise FilterError(f"unknown filter(s): {unknown}")

    def values(key: str) -> list[str]:
        return _values(key, raw.get(key))

    return {
        "title": _single("title", values("title")),
        "location": _unique(values("location")),
        "work_arrangement": _members(
            "work_arrangement", WorkArrangement, values("work_arrangement")
        ),
        "seniority": _members("seniority", Seniority, values("seniority")),
        "employment_type": _members("employment_type", EmploymentType, values("employment_type")),
        "date_posted": _member("date_posted", DatePosted, values("date_posted")),
        "years_experience": _single("years_experience", values("years_experience")),
        "industry": _unique(values("industry")),
        "terms": _unique(values("terms")),
    }


def load_filters() -> dict:
    """Persisted filter block, or DEFAULT_FILTERS when nothing is stored yet.

    A stored block that no longer parses raises FilterError instead of silently
    widening the search.
    """
    stored = SettingsRepo().get(KEY_DISCOVERY_FILTERS)

    if not stored:
        return dict(DEFAULT_FILTERS)

    try:
        block = json.loads(stored)
    except ValueError as exc:
        raise FilterError(f"persisted filters are not JSON: {exc}") from exc

    if not isinstance(block, dict):
        raise FilterError(f"persisted filters must be an object, got {type(block).__name__}")

    return parse_filters(block)


def save_filters(filters: Mapping[str, object]) -> dict:
    """Validate and persist all 9 keys; returns the stored block."""
    block = parse_filters(dict(filters))
    SettingsRepo().set(KEY_DISCOVERY_FILTERS, json.dumps(block))

    return block


def skill_variants(term: str) -> tuple[str, ...]:
    """Synonym group for a skill term; an unlisted term matches verbatim."""
    return SKILL_ALIASES.get(normalize(term), (term,))


def to_query(filters: Mapping[str, object]) -> dict:
    """Filter block -> `JobRepo.search(filters=...)` query spec.

    `years_experience` is persisted but never matched (handoff decision 3: no
    source reports an experience requirement, so a clause would empty results).
    """
    query = {
        key: filters.get(key, DEFAULT_FILTERS[key])
        for key in (
            "title",
            "location",
            "work_arrangement",
            "seniority",
            "employment_type",
            "industry",
        )
    }

    days = DATE_POSTED_DAYS.get(filters.get("date_posted") or "")

    if days:
        query["date_from"] = (utcnow().date() - timedelta(days=days)).isoformat()

    query["terms"] = [skill_variants(term) for term in filters.get("terms") or []]

    return query
