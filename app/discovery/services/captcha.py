"""The public challenge seam.

A solver answers a site challenge with the token the site asked for. Public
documentation presents the app as scraping public data, respecting robots.txt,
per-site terms, and law.
"""

from typing import Protocol, runtime_checkable

# Bumped whenever this protocol changes incompatibly; the registry refuses an
# installed solver that targets another version.
CAPTCHA_SEAM_VERSION = 1


@runtime_checkable
class CaptchaSolver(Protocol):
    """Installed implementation of a site challenge; registered under `applykit.captcha`."""

    seam_version: int  # MUST equal CAPTCHA_SEAM_VERSION

    def solve(self, challenge: str) -> str:
        """Return the token the challenge asks for; raise SourceError when it fails."""
        ...
