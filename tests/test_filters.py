"""Filter block: strict parse, persistence, and query-spec translation."""

from datetime import timedelta

import pytest

from app.data import DEFAULT_FILTERS, KEY_DISCOVERY_FILTERS, utcnow
from app.data.repositories import SettingsRepo
from app.discovery import SKILL_ALIASES
from app.discovery.errors import FilterError
from app.discovery.filters import load_filters, parse_filters, save_filters, to_query


def test_empty_block_is_defaults():
    assert set(parse_filters({})) == set(DEFAULT_FILTERS)
    assert parse_filters({}) == DEFAULT_FILTERS


def test_parse_result_is_a_copy():
    block = parse_filters({})
    block["title"] = "mutated"

    assert DEFAULT_FILTERS["title"] == ""


def test_unknown_key_rejected():
    with pytest.raises(FilterError, match="nope"):
        parse_filters({"nope": "1"})


def test_scalar_key_rejects_multiple():
    with pytest.raises(FilterError, match="single value"):
        parse_filters({"title": ["a", "b"]})


def test_scalar_key_rejects_non_string():
    with pytest.raises(FilterError):
        parse_filters({"title": 5})


def test_scalar_values_are_stripped():
    assert parse_filters({"title": "  engineer "})["title"] == "engineer"


def test_date_posted_validated():
    assert parse_filters({"date_posted": "7d"})["date_posted"] == "7d"
    assert parse_filters({"date_posted": ""})["date_posted"] == ""

    with pytest.raises(FilterError, match="must be one of.*'2d'"):
        parse_filters({"date_posted": "2d"})


def test_text_lists_dedupe_case_insensitively():
    assert parse_filters({"location": "EU"})["location"] == ["EU"]
    assert parse_filters({"location": [" EU ", "", "us", "US"]})["location"] == ["EU", "us"]


def test_enum_spellings_fold():
    assert parse_filters({"work_arrangement": ["Fully remote", "remote"]})["work_arrangement"] == [
        "remote"
    ]
    assert parse_filters({"seniority": "Sr."})["seniority"] == ["senior"]
    assert parse_filters({"employment_type": "Full-Time"})["employment_type"] == ["full_time"]


def test_enum_unknown_rejected():
    with pytest.raises(FilterError, match="must be one of.*'banana'"):
        parse_filters({"work_arrangement": "banana"})


def test_enum_blank_entry_is_absent():
    assert parse_filters({"work_arrangement": ["", "remote"]})["work_arrangement"] == ["remote"]


def test_terms_parse_verbatim():
    assert parse_filters({"terms": "GCP"})["terms"] == ["GCP"]


def test_query_terms_expand_synonym_groups():
    assert to_query(parse_filters({"terms": "GCP"}))["terms"] == [
        ("gcp", "google cloud", "google cloud platform")
    ]
    assert to_query(parse_filters({"terms": "rust"}))["terms"] == [("rust",)]
    assert SKILL_ALIASES["amazon web services"] == ("aws", "amazon web services")


def test_query_date_posted_bound():
    assert (
        to_query(parse_filters({"date_posted": "24h"}))["date_from"]
        == (utcnow().date() - timedelta(days=1)).isoformat()
    )
    assert "date_from" not in to_query(parse_filters({"date_posted": ""}))


def test_query_drops_years_experience():
    query = to_query(parse_filters({"years_experience": "5"}))

    assert "years_experience" not in query


def test_query_empty_block_has_no_conditions():
    query = to_query(parse_filters({}))

    assert query["title"] == ""
    assert query["location"] == []
    assert query["terms"] == []
    assert "date_from" not in query


def test_save_load_roundtrip():
    block = parse_filters({"location": "EU", "terms": "k8s"})
    save_filters(block)

    assert load_filters() == block


def test_load_defaults_when_unstored():
    assert load_filters() == DEFAULT_FILTERS


def test_load_rejects_unparsable_json():
    SettingsRepo().set(KEY_DISCOVERY_FILTERS, "{not json")

    with pytest.raises(FilterError, match="not JSON"):
        load_filters()


def test_load_rejects_non_object():
    SettingsRepo().set(KEY_DISCOVERY_FILTERS, "[1,2]")

    with pytest.raises(FilterError, match="must be an object"):
        load_filters()
