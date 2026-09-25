"""Canonical values for the exact-match job fields.

Filters match exactly, so stored values must come from a closed vocabulary. A
source may spell a value any way; `canonical()` folds known spellings onto the
vocabulary and keeps anything unrecognized verbatim.

  WorkArrangement.canonical("Fully remote")  -> "remote"
  WorkArrangement.canonical("Remote-OK")     -> "remote"
  Seniority.canonical("Sr.")                 -> "senior"
  Seniority.canonical("Chief of Staff")      -> "Chief of Staff"
  Seniority.canonical("   ")                 -> None

`location` and `industry_meta` have no vocabulary: Remotive sends region lists
("Northern America, LATAM, Europe, APAC") and free-text categories ("All
others"), so no alias table can canonicalize them.
"""

from __future__ import annotations

from enum import StrEnum

# Punctuation that separates words in source spellings: "Full-Time", "On-Site",
# "100% remote" -> "full time", "on site", "100 remote".
_SEPARATORS = str.maketrans(dict.fromkeys("-_/.,()%", " "))


def _key(value: str) -> str:
    """Casefold, drop separator punctuation, collapse whitespace."""
    return " ".join(value.casefold().translate(_SEPARATORS).split())


class _Vocabulary(StrEnum):
    """Enum whose source spellings fold onto its members."""

    @classmethod
    def canonical(cls, value: str | None) -> str | None:
        """Fold `value` onto a member value; unknown spellings stay verbatim.

        None and blank values become None (the render layer shows `Not provided`).
        The return is the enum member, a `str` subclass, so it stores and
        serializes unchanged.
        """
        if value is None:
            return None

        text = value.strip()

        if not text:
            return None

        return _ALIASES[cls].get(_key(text), text)


class WorkArrangement(_Vocabulary):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class EmploymentType(_Vocabulary):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"  # observed in the Remotive public API
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    OTHER = "other"


class Seniority(_Vocabulary):
    """Bands shared with seeding (3.3) and the UI (3.8); year ranges live in 3.3."""

    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"


# Alias keys are `_key(value)`, so every member value MUST appear here too
# ("full_time" -> key "full time"), or it could not round-trip.
_ALIASES: dict[type[_Vocabulary], dict[str, str]] = {
    WorkArrangement: {
        "remote": WorkArrangement.REMOTE,
        "fully remote": WorkArrangement.REMOTE,
        "100 remote": WorkArrangement.REMOTE,
        "remote ok": WorkArrangement.REMOTE,
        "work from home": WorkArrangement.REMOTE,
        "wfh": WorkArrangement.REMOTE,
        "hybrid": WorkArrangement.HYBRID,
        "remote hybrid": WorkArrangement.HYBRID,
        "partially remote": WorkArrangement.HYBRID,
        "onsite": WorkArrangement.ONSITE,
        "on site": WorkArrangement.ONSITE,
        "in office": WorkArrangement.ONSITE,
        "office": WorkArrangement.ONSITE,
    },
    EmploymentType: {
        "full time": EmploymentType.FULL_TIME,
        "part time": EmploymentType.PART_TIME,
        "contract": EmploymentType.CONTRACT,
        "contractor": EmploymentType.CONTRACT,
        "freelance": EmploymentType.FREELANCE,
        "freelancer": EmploymentType.FREELANCE,
        "internship": EmploymentType.INTERNSHIP,
        "intern": EmploymentType.INTERNSHIP,
        "temporary": EmploymentType.TEMPORARY,
        "temp": EmploymentType.TEMPORARY,
        "other": EmploymentType.OTHER,
    },
    Seniority: {
        "entry": Seniority.ENTRY,
        "entry level": Seniority.ENTRY,
        "junior": Seniority.ENTRY,
        "jr": Seniority.ENTRY,
        "graduate": Seniority.ENTRY,
        "mid": Seniority.MID,
        "mid level": Seniority.MID,
        "intermediate": Seniority.MID,
        "senior": Seniority.SENIOR,
        "sr": Seniority.SENIOR,
        "staff": Seniority.LEAD,
        "lead": Seniority.LEAD,
        "principal": Seniority.LEAD,
        "head": Seniority.LEAD,
        "director": Seniority.LEAD,
        "manager": Seniority.LEAD,
    },
}
