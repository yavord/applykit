"""Export settings contract: strict query-param parsing for the export drawer."""

from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum

from app.resumes.errors import SettingsError


class ExportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class FontFamily(StrEnum):
    WORK_SANS = "work_sans"
    TIMES_NEW_ROMAN = "times_new_roman"
    HELVETICA = "helvetica"


class HeaderAlign(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class EducationOrder(StrEnum):
    DEGREE_FIRST = "degree_first"
    INSTITUTION_FIRST = "institution_first"


class SkillsLayout(StrEnum):
    INLINE = "inline"
    GROUPED = "grouped"
    COLUMN = "column"


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """Drawer fields; names mirror query params"""

    format: ExportFormat = ExportFormat.PDF
    font_family: FontFamily = FontFamily.WORK_SANS
    name_size: int = 24
    header_size: int = 14
    subheader_size: int = 12
    body_size: int = 11
    header_align: HeaderAlign = HeaderAlign.LEFT
    education_order: EducationOrder = EducationOrder.DEGREE_FIRST
    skills_layout: SkillsLayout = SkillsLayout.GROUPED
    section_spacing: int = 4
    entry_spacing: int = 3
    line_spacing: int = 12
    margin_top: int = 36
    margin_bottom: int = 36
    margin_side: int = 36
    align_justify: bool = False


# Inclusive bounds per int field; the contract's accepted ranges.
_INT_FIELDS: dict[str, tuple[int, int]] = {
    "name_size": (16, 30),
    "header_size": (10, 20),
    "subheader_size": (8, 18),
    "body_size": (8, 14),
    "section_spacing": (0, 10),
    "entry_spacing": (0, 10),
    "line_spacing": (10, 15),
    "margin_top": (10, 50),
    "margin_bottom": (10, 50),
    "margin_side": (30, 50),
}

_ENUM_FIELDS: dict[str, type[StrEnum]] = {
    "format": ExportFormat,
    "font_family": FontFamily,
    "header_align": HeaderAlign,
    "education_order": EducationOrder,
    "skills_layout": SkillsLayout,
}

_ALIGN_JUSTIFY = "align_justify"

_BOOL_STRINGS = {"true": True, "false": False}


def _parse_int(key: str, raw: str, lo: int, hi: int) -> int:
    try:
        value = int(raw)
    except ValueError as e:
        raise SettingsError(f"export setting '{key}' must be an integer, got '{raw}'") from e

    if not lo <= value <= hi:
        raise SettingsError(f"export setting '{key}' out of range [{lo}, {hi}]: {value}")

    return value


def _parse_enum(key: str, raw: str, enum_cls: type[StrEnum]) -> StrEnum:
    try:
        return enum_cls(raw)
    except ValueError as e:
        options = [member.value for member in enum_cls]
        raise SettingsError(f"export setting '{key}' must be one of {options}, got '{raw}'") from e


def _parse_bool(key: str, raw: str) -> bool:
    try:
        return _BOOL_STRINGS[raw]
    except KeyError as e:
        raise SettingsError(f"export setting '{key}' must be 'true' or 'false', got '{raw}'") from e


def parse_settings(params: Mapping[str, str]) -> ExportSettings:
    """Strict parse of query params; unknown key or invalid value raises SettingsError."""

    values: dict[str, int | bool | StrEnum] = {}

    for key, raw in params.items():
        if key in _INT_FIELDS:
            lo, hi = _INT_FIELDS[key]
            values[key] = _parse_int(key, raw, lo, hi)
        elif key in _ENUM_FIELDS:
            values[key] = _parse_enum(key, raw, _ENUM_FIELDS[key])
        elif key == _ALIGN_JUSTIFY:
            values[key] = _parse_bool(key, raw)
        else:
            raise SettingsError(f"unknown export setting: {key}")

    return ExportSettings(**values)


def settings_to_params(s: ExportSettings) -> dict[str, str]:
    """Canonical serialization: all 16 keys, str(int), enum .value, bool as 'true'/'false'."""

    params: dict[str, str] = {}

    for field in fields(s):
        value = getattr(s, field.name)
        if isinstance(value, bool):
            params[field.name] = "true" if value else "false"
        elif isinstance(value, StrEnum):
            params[field.name] = value.value
        else:
            params[field.name] = str(value)

    return params
