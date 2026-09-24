"""Job discovery: the source seam, its registry, and the public error types.

No SourceAdapter or CaptchaSolver implementation ships in this tree; real
implementations are installed packages that register entry points.
"""

from app.discovery.errors import (
    DiscoveryError,
    FilterError,
    SourceConfigError,
    SourceError,
    SourceVersionError,
)
from app.discovery.services.captcha import CAPTCHA_SEAM_VERSION, CaptchaSolver
from app.discovery.services.filters import (
    SKILL_ALIASES,
    DatePosted,
    load_filters,
    parse_filters,
    save_filters,
    to_query,
)
from app.discovery.services.job_service import list_jobs
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
    "DatePosted",
    "DiscoveryError",
    "EmploymentType",
    "FilterError",
    "SKILL_ALIASES",
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
    "list_jobs",
    "load_captcha",
    "load_filters",
    "load_sources",
    "parse_filters",
    "save_filters",
    "to_query",
]
