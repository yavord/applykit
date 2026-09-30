"""Conformance of the job sources actually installed (S6)."""

from importlib.metadata import entry_points

import pytest

from app.discovery.registry import SOURCES_GROUP, load_sources
from app.discovery.source_adapter import SOURCE_SEAM_VERSION, SourceAdapter


def test_installed_sources_load_and_conform():
    points = list(entry_points(group=SOURCES_GROUP))

    if not points:
        pytest.skip("no job source installed")

    adapters = load_sources()

    assert len(adapters) == len(points)

    for adapter in adapters:
        assert isinstance(adapter, SourceAdapter)
        assert adapter.seam_version == SOURCE_SEAM_VERSION
