"""Job discovery: the source seam, its registry, and the public error types.

No SourceAdapter or CaptchaSolver implementation ships in this tree; real
implementations are installed packages that register entry points.
"""

from app.discovery.errors import (
    DiscoveryError,
    SourceConfigError,
    SourceError,
    SourceVersionError,
)
from app.discovery.services.captcha import CAPTCHA_SEAM_VERSION, CaptchaSolver
from app.discovery.services.registry import load_captcha, load_sources
from app.discovery.services.source_adapter import (
    SOURCE_FETCH_LIMIT,
    SOURCE_SEAM_VERSION,
    SourceAdapter,
    SourceJob,
    SourceQuery,
)
from app.discovery.services.vocab import EmploymentType, Seniority, WorkArrangement

__all__ = [
    "CAPTCHA_SEAM_VERSION",
    "CaptchaSolver",
    "DiscoveryError",
    "EmploymentType",
    "SOURCE_FETCH_LIMIT",
    "SOURCE_SEAM_VERSION",
    "Seniority",
    "SourceAdapter",
    "SourceConfigError",
    "SourceError",
    "SourceJob",
    "SourceQuery",
    "SourceVersionError",
    "WorkArrangement",
    "load_captcha",
    "load_sources",
]
