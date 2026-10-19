import json
from pathlib import Path


DEFAULTS = {
    "save_root": None,          # None = app directory
    "cloud_provider": "ask",    # "ask" | "github" | "gdrive"
}


class SettingsStore:
    """Simple JSON-backed app settings."""

    def __init__(self, app_dir):
        self.app_dir = Path(app_dir).resolve()
        self.path = self.app_dir / "settings.json"
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4)
        except OSError:
            pass

    # --- accessors ------------------------------------------------------
    def get_save_root(self):
        raw = self._data.get("save_root")
        if not raw:
            return self.app_dir
        return Path(raw).resolve()

    def set_save_root(self, path):
        self._data["save_root"] = str(Path(path).resolve()) \
            if path is not None else None
        self.save()

    def get_cloud_provider(self):
        return self._data.get("cloud_provider", "ask")

    def set_cloud_provider(self, name):
        if name not in ("ask", "github", "gdrive"):
            raise ValueError(f"Unknown provider: {name}")
        self._data["cloud_provider"] = name
        self.save()