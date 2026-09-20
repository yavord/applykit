"""Discovery capability errors: source failures and unset seams."""


class DiscoveryError(Exception):
    """Base for discovery failures that surface to the user."""


class SourceError(DiscoveryError):
    """A source could not return records (network, API, malformed payload)."""


class SourceConfigError(DiscoveryError):
    """A required seam (source adapter or captcha solver) is not installed."""


class SourceVersionError(SourceConfigError):
    """An installed implementation targets a different seam version."""
