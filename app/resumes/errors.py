"""Resume capability errors: recoverable imports plus CRUD failures with HTTP status."""


class UnsupportedFormatError(Exception):
    """File is not a supported resume format; rejected before any write."""


class ExtractionError(Exception):
    """File matches a supported format but cannot be read (corrupt/encrypted)."""


class ResumeError(Exception):
    """Resume CRUD failure; subclass status_code drives the HTTP response."""

    status_code = 500  # overridden per subclass


class ResumeNotFoundError(ResumeError):
    status_code = 404


class InvalidSectionsError(ResumeError):
    status_code = 400


class DuplicateResumeError(ResumeError):
    status_code = 409


class ActiveResumeError(ResumeError):
    status_code = 409
