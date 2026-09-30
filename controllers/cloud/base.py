from abc import ABC, abstractmethod


class CloudProvider(ABC):
    """Abstract base for any cloud provider (GitHub, Google Drive, ...)."""

    NAME = "Cloud"

    @abstractmethod
    def detect(self):
        """Probe the system for authentication and return an info dict."""

    @abstractmethod
    def is_ready(self):
        """Return True if the provider is authenticated and usable."""

    @abstractmethod
    def status_text(self):
        """Human-readable one-line status for the UI."""

    @abstractmethod
    def upload_all(self, progress_cb=None):
        """Upload every save. `progress_cb(msg: str)` is optional."""