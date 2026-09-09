"""Export settings contract tests: defaults, round-trips, bounds, rejections."""

import pytest

from app.resumes.errors import SettingsError
from app.resumes.services.settings import (
    EducationOrder,
    ExportFormat,
    ExportSettings,
    FontFamily,
    HeaderAlign,
    SkillsLayout,
    parse_settings,
    settings_to_params,
)

# One non-default valid value per field; parametrized round-trip builds on these.
_NON_DEFAULT: dict[str, object] = {
    "format": ExportFormat.DOCX,
    "font_family": FontFamily.HELVETICA,
    "name_size": 16,
    "header_size": 20,
    "subheader_size": 8,
    "body_size": 14,
    "header_align": HeaderAlign.RIGHT,
    "education_order": EducationOrder.INSTITUTION_FIRST,
    "skills_layout": SkillsLayout.COLUMN,
    "section_spacing": 0,
    "entry_spacing": 10,
    "line_spacing": 15,
    "margin_top": 50,
    "margin_bottom": 10,
    "margin_side": 30,
    "align_justify": True,
}

# Inclusive bounds per int field, mirroring the contract table.
_INT_RANGES: list[tuple[str, int, int]] = [
    ("name_size", 16, 30),
    ("header_size", 10, 20),
    ("subheader_size", 8, 18),
    ("body_size", 8, 14),
    ("section_spacing", 0, 10),
    ("entry_spacing", 0, 10),
    ("line_spacing", 10, 15),
    ("margin_top", 10, 50),
    ("margin_bottom", 10, 50),
    ("margin_side", 30, 50),
]

_ENUMS: list[tuple[str, type]] = [
    ("format", ExportFormat),
    ("font_family", FontFamily),
    ("header_align", HeaderAlign),
    ("education_order", EducationOrder),
    ("skills_layout", SkillsLayout),
]


def test_defaults():
    settings = parse_settings({})

    assert settings == ExportSettings()
    assert settings.format is ExportFormat.PDF
    assert settings.font_family is FontFamily.WORK_SANS
    assert settings.margin_side == 36


@pytest.mark.parametrize("field", list(_NON_DEFAULT))
def test_round_trip(field):
    settings = ExportSettings(**{field: _NON_DEFAULT[field]})

    assert parse_settings(settings_to_params(settings)) == settings


def test_full_dict_round_trip():
    params = settings_to_params(ExportSettings())

    assert len(params) == 16
    assert settings_to_params(parse_settings(params)) == params


@pytest.mark.parametrize(("key", "lo", "hi"), _INT_RANGES)
def test_bounds(key, lo, hi):
    assert getattr(parse_settings({key: str(lo)}), key) == lo
    assert getattr(parse_settings({key: str(hi)}), key) == hi

    for value in (lo - 1, hi + 1):
        with pytest.raises(SettingsError) as excinfo:
            parse_settings({key: str(value)})

        assert key in str(excinfo.value)


@pytest.mark.parametrize(
    ("params", "needles"),
    [
        ({"bogus": "1"}, ("unknown export setting", "bogus")),
        ({"name_size": "abc"}, ("name_size", "must be an integer", "got 'abc'")),
        ({"name_size": ""}, ("name_size", "must be an integer")),
        (
            {"format": "ps"},
            ("format", "must be one of", "['pdf', 'docx']", "got 'ps'"),
        ),
        ({"format": ""}, ("format", "must be one of")),
        (
            {"align_justify": "yes"},
            ("align_justify", "must be 'true' or 'false'", "got 'yes'"),
        ),
        ({"align_justify": ""}, ("align_justify", "must be 'true' or 'false'")),
        ({"margin_top": "9"}, ("margin_top", "out of range [10, 50]", ": 9")),
    ],
)
def test_rejection(params, needles):
    with pytest.raises(SettingsError) as excinfo:
        parse_settings(params)

    for needle in needles:
        assert needle in str(excinfo.value)


@pytest.mark.parametrize(("key", "enum_cls"), _ENUMS)
def test_enum_members(key, enum_cls):
    for member in enum_cls:
        settings = parse_settings({key: member.value})

        assert getattr(settings, key) is member
        assert settings_to_params(settings)[key] == member.value
