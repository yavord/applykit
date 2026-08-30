"""Recoverable import errors: caller shows the message, nothing is persisted."""


class UnsupportedFormatError(Exception):
    """File is not a supported resume format; rejected before any write."""


class ExtractionError(Exception):
    """File matches a supported format but cannot be read (corrupt/encrypted)."""
