"""Custom exceptions for the Aetherix backend."""


class NotConfiguredError(Exception):
    """Raised when a required external service is not configured.

    This typically means the necessary environment variables (API keys, etc.)
    have not been set. Operations requiring the service cannot proceed.
    """

    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__(
            f"{service} is not configured. "
            f"Please set the required environment variables."
        )
