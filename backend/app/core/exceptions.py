"""Custom exceptions for the Aetherix backend."""


class NotConfiguredError(Exception):
    """Raised when a required external service is not configured.

    Typically means required environment variables (API keys, phone numbers, etc.)
    have not been set, or a required value is invalid.
    """


class AnomalyDetectionError(Exception):
    """Raised when the anomaly detection service encounters a non-recoverable error.

    Distinct from table-not-found (ProgrammingError) which is handled silently
    with a fallback. This covers DB connection failures and other unexpected errors.
    """
