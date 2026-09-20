"""Entry-point registry for the two seams; nothing here names a private module.

An installed package registers:
  applykit.sources   -> zero-argument callable returning a SourceAdapter
  applykit.captcha   -> zero-argument callable returning a CaptchaSolver
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points

from app.discovery.errors import SourceConfigError, SourceVersionError
from app.discovery.services.captcha import CAPTCHA_SEAM_VERSION, CaptchaSolver
from app.discovery.services.source_adapter import SOURCE_SEAM_VERSION, SourceAdapter

SOURCES_GROUP = "applykit.sources"
CAPTCHA_GROUP = "applykit.captcha"

_NO_SOURCES = (
    f"no job source installed: install a package that registers a '{SOURCES_GROUP}' entry point"
)
_NO_CAPTCHA = (
    f"no captcha solver installed: install a package that registers a '{CAPTCHA_GROUP}' entry point"
)


def _discover(group: str) -> list[EntryPoint]:
    """Entry points of one seam, name-ordered so repeated runs are reproducible."""
    return sorted(entry_points(group=group), key=lambda ep: ep.name)


def _instantiate(ep: EntryPoint) -> object:
    """Load an entry point and call its zero-argument factory."""
    factory = ep.load()

    if not callable(factory):
        raise SourceConfigError(f"entry point '{ep.name}' ({ep.group}) is not a callable factory")

    try:
        return factory()
    except Exception as exc:
        raise SourceConfigError(
            f"entry point '{ep.name}' ({ep.group}) failed to load: {exc}"
        ) from exc


def _check_version(ep: EntryPoint, version: object, expected: int) -> None:
    """Refuse an implementation built against another seam version.

    The message names the entry point: that is the registration a user must
    update, and unlike `adapter.name` it always exists.
    """
    if version != expected:
        raise SourceVersionError(
            f"entry point '{ep.name}' ({ep.group}) targets seam version {version!r}; "
            f"this app expects {expected}"
        )


def load_sources() -> list[SourceAdapter]:
    """Every installed source, in entry-point name order.

    Raises SourceConfigError when none is installed or a plugin misbehaves;
    callers surface the message instead of a traceback.
    """
    points = _discover(SOURCES_GROUP)

    if not points:
        raise SourceConfigError(_NO_SOURCES)

    adapters: list[SourceAdapter] = []

    for ep in points:
        adapter = _instantiate(ep)

        if not isinstance(adapter, SourceAdapter):
            raise SourceConfigError(f"entry point '{ep.name}' ({ep.group}) is not a SourceAdapter")

        # isinstance only checks attribute presence; an empty name is unusable.
        if not str(adapter.name).strip():
            raise SourceConfigError(f"source '{ep.name}' ({ep.group}) has an empty name")

        _check_version(ep, adapter.seam_version, SOURCE_SEAM_VERSION)

        if any(adapter.name == seen.name for seen in adapters):
            raise SourceConfigError(f"two installed sources share the name '{adapter.name}'")

        adapters.append(adapter)

    return adapters


def load_captcha() -> CaptchaSolver:
    """The installed challenge solver; adapters call it lazily, per challenge.

    The lowest-named registered solver wins. Raises SourceConfigError when none
    is installed.
    """
    points = _discover(CAPTCHA_GROUP)

    if not points:
        raise SourceConfigError(_NO_CAPTCHA)

    solver = _instantiate(points[0])

    if not isinstance(solver, CaptchaSolver):
        raise SourceConfigError(
            f"entry point '{points[0].name}' ({CAPTCHA_GROUP}) is not a CaptchaSolver"
        )

    _check_version(points[0], solver.seam_version, CAPTCHA_SEAM_VERSION)

    return solver
