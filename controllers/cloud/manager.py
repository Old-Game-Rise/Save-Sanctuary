from pathlib import Path

from controllers.cloud.github_provider import GitHubProvider


class CloudManager:
    """Owns the available cloud providers and delegates uploads/downloads."""

    def __init__(self, app_dir):
        self.app_dir = Path(app_dir).resolve()
        self.providers = {
            "github": GitHubProvider(self.app_dir),
            # "gdrive": GDriveProvider(self.app_dir),   # later
        }
        self.active = "github"

    def get_provider(self):
        return self.providers[self.active]

    def upload_all(self, progress_cb=None):
        return self.get_provider().upload_all(progress_cb)

    def pull_all(self, progress_cb=None):
        return self.get_provider().pull_all(progress_cb)

    def compare_with_remote(self, progress_cb=None):
        return self.get_provider().compare_with_remote(progress_cb)