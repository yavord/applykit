"""Registry behavior and the public seam surface."""

from importlib.metadata import EntryPoint

import pytest

from app.data.repositories import JobData
from app.discovery import (
    CAPTCHA_SEAM_VERSION,
    SOURCE_SEAM_VERSION,
    CaptchaSolver,
    SourceAdapter,
    SourceConfigError,
    SourceJob,
    SourceQuery,
    SourceVersionError,
    load_captcha,
    load_sources,
)
from app.discovery.services import registry
from tests.fakes import (
    FAKE_JOB,
    FakeAdapter,
    RecordingSolver,
    install_entries,
    stub_captcha,
    stub_source,
)


def test_fakes_implement_the_protocols():
    assert isinstance(FakeAdapter(), SourceAdapter)
    assert isinstance(RecordingSolver(), CaptchaSolver)


def test_unset_source_seam_raises_config_error(monkeypatch):
    install_entries(monkeypatch)

    with pytest.raises(SourceConfigError) as exc:
        load_sources()

    assert registry.SOURCES_GROUP in str(exc.value)


def test_unset_captcha_seam_raises_config_error(monkeypatch):
    install_entries(monkeypatch)

    with pytest.raises(SourceConfigError) as exc:
        load_captcha()

    assert registry.CAPTCHA_GROUP in str(exc.value)


def test_registered_fake_runs_through_registry(monkeypatch):
    entry = EntryPoint(name="fake", value="tests.fakes:FakeAdapter", group=registry.SOURCES_GROUP)
    install_entries(monkeypatch, entry)

    (adapter,) = load_sources()
    assert adapter.name == "fake"

    query = SourceQuery(filters={"title": "engineer"}, limit=7)
    assert adapter.fetch(query) == [FAKE_JOB]
    assert adapter.queries == [query]


def test_groups_load_independently(monkeypatch):
    install_entries(monkeypatch, stub_captcha("solver", RecordingSolver))

    assert load_captcha().solve("c1") == "test-token"

    with pytest.raises(SourceConfigError):
        load_sources()


def test_sources_load_in_entry_point_name_order(monkeypatch):
    install_entries(
        monkeypatch,
        stub_source("b", lambda: FakeAdapter(name="b")),
        stub_source("a", lambda: FakeAdapter(name="a")),
    )

    assert [a.name for a in load_sources()] == ["a", "b"]


def test_lowest_named_solver_wins(monkeypatch):
    install_entries(
        monkeypatch,
        stub_captcha("b", lambda: RecordingSolver("beta")),
        stub_captcha("a", lambda: RecordingSolver("alpha")),
    )

    assert load_captcha().token == "alpha"


def test_duplicate_source_names_rejected(monkeypatch):
    install_entries(
        monkeypatch,
        stub_source("one", lambda: FakeAdapter()),
        stub_source("two", lambda: FakeAdapter()),
    )

    with pytest.raises(SourceConfigError) as exc:
        load_sources()

    assert "fake" in str(exc.value)


def test_non_callable_entry_point_rejected(monkeypatch):
    install_entries(monkeypatch, stub_source("bad", 42))

    with pytest.raises(SourceConfigError) as exc:
        load_sources()

    assert "bad" in str(exc.value)


def test_non_conforming_entry_point_rejected(monkeypatch):
    install_entries(monkeypatch, stub_source("bad", object))

    with pytest.raises(SourceConfigError):
        load_sources()


def test_empty_source_name_rejected(monkeypatch):
    install_entries(monkeypatch, stub_source("bad", lambda: FakeAdapter(name="  ")))

    with pytest.raises(SourceConfigError):
        load_sources()


def test_factory_failure_becomes_config_error(monkeypatch):
    def boom():
        raise RuntimeError("no api key")

    install_entries(monkeypatch, stub_source("bad", boom))

    with pytest.raises(SourceConfigError) as exc:
        load_sources()

    assert "no api key" in str(exc.value)


def test_source_version_mismatch_rejected(monkeypatch):
    install_entries(
        monkeypatch, stub_source("old", lambda: FakeAdapter(seam_version=SOURCE_SEAM_VERSION + 1))
    )

    with pytest.raises(SourceVersionError) as exc:
        load_sources()

    assert str(exc.value) == (
        "entry point 'old' (applykit.sources) targets seam version 2; this app expects 1"
    )


def test_captcha_version_mismatch_rejected(monkeypatch):
    class OldSolver(RecordingSolver):
        seam_version = CAPTCHA_SEAM_VERSION + 1

    install_entries(monkeypatch, stub_captcha("old", OldSolver))

    with pytest.raises(SourceVersionError) as exc:
        load_captcha()

    assert "entry point 'old'" in str(exc.value)
    assert "seam version" in str(exc.value)


def test_reject_reason_for_missing_identity():
    assert SourceJob(title="", company="Acme").reject_reason() == "missing title"
    assert SourceJob(title="Engineer", company="   ").reject_reason() == "missing company"
    assert SourceJob(title="Engineer", company="Acme").reject_reason() is None


def test_reject_reason_for_bad_date():
    assert (
        "posted_date"
        in SourceJob(
            title="Engineer", company="Acme", posted_date="2024-05-01T10:00:00"
        ).reject_reason()
    )
    assert (
        SourceJob(title="Engineer", company="Acme", posted_date="2024-05-01").reject_reason()
        is None
    )


def test_bad_record_never_raises_on_construction():
    job = SourceJob(title="", company="", posted_date="nope")

    assert job.reject_reason() is not None


def test_source_job_preserves_nulls():
    job = SourceJob(title="Engineer", company="Acme")

    assert job.location is None
    assert job.experience_req is None
    assert job.responsibilities is None
    assert job.canonical_url is None
    assert job.industry_meta is None


def test_source_job_fields_are_storable_columns():
    for field_name in SourceJob.__dataclass_fields__:
        assert field_name in JobData.__dataclass_fields__
