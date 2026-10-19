from pathlib import Path
from controllers.cloud.github_provider import GitHubProvider
from controllers.cloud.gdrive_provider import GDriveProvider


class CloudManager:
    def __init__(self, app_dir, save_root=None):
        self.app_dir = Path(app_dir).resolve()
        self.save_root = Path(save_root or self.app_dir).resolve()
        self._build_providers()
        self.active = "github"

    def _build_providers(self):
        self.providers = {
            "github": GitHubProvider(self.app_dir, self.save_root),
            "gdrive": GDriveProvider(self.app_dir, self.save_root),
        }

    def rebuild(self, save_root):
        """Rebuild providers after the save root changes."""
        self.save_root = Path(save_root).resolve()
        self._build_providers()

    def set_active(self, name):
        if name in self.providers:
            self.active = name

    def get_provider(self):
        return self.providers[self.active]

    def upload_all(self, progress_cb=None):
        return self.get_provider().upload_all(progress_cb)

    def pull_all(self, progress_cb=None):
        return self.get_provider().pull_all(progress_cb)

    def compare_with_remote(self, progress_cb=None):
        return self.get_provider().compare_with_remote(progress_cb)