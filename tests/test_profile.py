"""ProfileRepo behavior: value round-trip and fit-staleness version."""

from app.data.repositories import ProfileRepo, SettingsRepo


def test_set_get_round_trip():
    repo = ProfileRepo()

    repo.set("name", "ggg")
    repo.set("links", '["https://x.io"]')

    assert repo.get("name") == "ggg"
    assert repo.get("links") == '["https://x.io"]'
    assert repo.get("missing") is None


def test_all_returns_every_key():
    repo = ProfileRepo()

    repo.set("name", "ggg")
    repo.set("email", "g@x.io")

    assert repo.all() == {"name": "ggg", "email": "g@x.io"}


def test_version_bumps_on_every_set():
    repo = ProfileRepo()

    assert repo.version() == 0
    repo.set("name", "ggg")
    assert repo.version() == 1
    repo.set("name", "ggg 2")
    assert repo.version() == 2

    # Repeated value still bumps: profile changed, fit cache is stale.
    repo.set("name", "ggg 2")
    assert repo.version() == 3


def test_settings_repo_independent_keys():
    settings = SettingsRepo()

    assert settings.get("discovery_filters") is None
    settings.set("discovery_filters", '{"title": "engineer"}')

    assert settings.get("discovery_filters") == '{"title": "engineer"}'
    assert ProfileRepo().version() == 0  # settings writes never bump profile version
