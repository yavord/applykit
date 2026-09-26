"""Discovery capability errors: source failures and unset seams."""


class DiscoveryError(Exception):
    """Base for discovery failures that surface to the user."""


class SourceError(DiscoveryError):
    """A source could not return records (network, API, malformed payload)."""


class SourceConfigError(DiscoveryError):
    """A required seam (source adapter or captcha solver) is not installed."""


class SourceVersionError(SourceConfigError):
    """An installed implementation targets a different seam version."""


class FilterError(DiscoveryError):
    """Invalid discovery filter block; 422."""

    status_code = 422


class NoActiveResumeError(DiscoveryError):
    """A run needs an active resume snapshot; 409."""

    status_code = 409
