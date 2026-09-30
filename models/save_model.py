import json
import shutil
from pathlib import Path
from PIL import Image
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _rel_to_app(self, abs_path):
    """Return a POSIX-style path relative to the app directory."""
    try:
        return Path(abs_path).resolve().relative_to(self.base_dir).as_posix()
    except ValueError:
        # Path is outside the app dir — keep it as-is (shouldn't normally happen)
        return Path(abs_path).as_posix()


class SaveModel:
    """Handles all filesystem operations for game saves."""

    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
        self.base_dir = Path(base_dir)
        self.user_saves_dir = self.base_dir / "user saves"
        self.thumbnails_dir = self.base_dir / "thumbnails"
        self.user_saves_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Reading
    # ------------------------------------------------------------------ #
    def list_saves(self):
        saves = []
        if not self.user_saves_dir.exists():
            return saves
        for folder in sorted(self.user_saves_dir.iterdir()):
            if not folder.is_dir():
                continue
            config_file = folder / "config.json"
            if not config_file.exists():
                continue
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            config.setdefault("description", "")
            config.setdefault("updated_at", None)
            config.setdefault("uploaded_at", None)
            config["folder_name"] = folder.name
            config["folder_path"] = str(folder)
            saves.append(config)
        return saves

    def get_config(self, folder_name):
        config_file = self.user_saves_dir / folder_name / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _unique_folder_name(self, name):
        if not (self.user_saves_dir / name).exists():
            return name
        counter = 1
        while (self.user_saves_dir / f"{name}_{counter}").exists():
            counter += 1
        return f"{name}_{counter}"

    def _save_thumbnail(self, source, folder_name):
        """Crop to 1:1, resize to 256x256, save as PNG and return a
        path relative to the app directory."""
        dest = self.thumbnails_dir / f"{folder_name}.png"

        with Image.open(source) as src:
            img = src.convert("RGBA")

        w, h = img.size
        size = min(w, h)
        left = (w - size) // 2
        top = (h - size) // 2
        img = img.crop((left, top, left + size, top + size))
        img = img.resize((256, 256), Image.LANCZOS)

        tmp = dest.with_suffix(".png.tmp")
        img.save(tmp, "PNG")
        img.close()
        tmp.replace(dest)

        # Store relative to the app directory, POSIX-style.
        return _rel_to_app(self, dest)
    
    def _copy_contents(self, src, dst):
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                if target.exists():
                    self._copy_contents(item, target)
                else:
                    shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

    # ------------------------------------------------------------------ #
    # Import
    # ------------------------------------------------------------------ #
    def import_save(self, source_path, title, folder_name,
                    thumbnail_source=None, description=""):
        source_path = Path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        final_folder_name = self._unique_folder_name(folder_name)
        target_dir = self.user_saves_dir / final_folder_name
        target_dir.mkdir(parents=True, exist_ok=False)

        save_dir = target_dir / "save"
        is_dir = source_path.is_dir()

        if is_dir:
            shutil.copytree(source_path, save_dir)
        else:
            save_dir.mkdir()
            shutil.copy2(source_path, save_dir / source_path.name)

        thumb_path = None
        if thumbnail_source:
            thumb_path = self._save_thumbnail(thumbnail_source, final_folder_name)

        now = _now_iso()
        config = {
            "title": title,
            "description": description,
            "thumbnail": thumb_path,
            "original_path": str(source_path),
            "original_is_dir": is_dir,
            "updated_at": now,
            "uploaded_at": None,
        }
        with open(target_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        return final_folder_name

    # ------------------------------------------------------------------ #
    # Update / Edit
    # ------------------------------------------------------------------ #
    def update_save(self, old_folder_name, new_title, new_folder_name,
                    new_thumbnail_path=None, thumbnail_changed=False,
                    description=None):
        old_dir = self.user_saves_dir / old_folder_name
        with open(old_dir / "config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        folder_renamed = new_folder_name != old_folder_name
        if folder_renamed:
            final_name = self._unique_folder_name(new_folder_name)
            new_dir = self.user_saves_dir / final_name
            old_dir.rename(new_dir)
        else:
            final_name = old_folder_name
            new_dir = old_dir

        old_thumb = config.get("thumbnail")

        if thumbnail_changed and new_thumbnail_path:
            if old_thumb:
                old_abs = self.resolve_thumbnail(old_thumb)
                if old_abs and old_abs.exists() and old_abs != Path(new_thumbnail_path):
                    try:
                        old_abs.unlink()
                    except OSError:
                        pass
            config["thumbnail"] = self._save_thumbnail(new_thumbnail_path, final_name)
        elif folder_renamed and old_thumb:
            old_thumb_path = self.resolve_thumbnail(old_thumb)
            if old_thumb_path and old_thumb_path.exists():
                new_thumb_path = self.thumbnails_dir / f"{final_name}.png"
                if old_thumb_path != new_thumb_path:
                    if new_thumb_path.exists():
                        try:
                            new_thumb_path.unlink()
                        except OSError:
                            pass
                    old_thumb_path.rename(new_thumb_path)
                config["thumbnail"] = _rel_to_app(self, new_thumb_path)
            else:
                config["thumbnail"] = None

        config["title"] = new_title
        if description is not None:
            config["description"] = description
        config["updated_at"] = _now_iso()
        with open(new_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        return final_name

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete_save(self, folder_name):
        folder = self.user_saves_dir / folder_name
        if not folder.exists():
            raise FileNotFoundError(f"Save '{folder_name}' does not exist.")

        config_file = folder / "config.json"
        thumb_path = None
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    thumb_path = json.load(f).get("thumbnail")
            except (OSError, json.JSONDecodeError):
                thumb_path = None

        shutil.rmtree(folder, ignore_errors=False)

        if thumb_path:
            tp = Path(thumb_path)
            if tp.exists() and tp.is_file():
                try:
                    tp.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def export_save(self, folder_name, target_path=None):
        folder = self.user_saves_dir / folder_name
        config = self.get_config(folder_name)
        save_dir = folder / "save"
        is_dir = config.get("original_is_dir", True)

        if target_path is None:
            target = Path(config["original_path"])
            if is_dir:
                if target.exists():
                    self._copy_contents(save_dir, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(save_dir, target)
            else:
                files = [f for f in save_dir.iterdir() if f.is_file()]
                if not files:
                    raise FileNotFoundError("No file found inside save folder.")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(files[0], target)
        else:
            target = Path(target_path)
            if is_dir:
                dest = target / folder_name if target.is_dir() else target
                if dest.exists():
                    self._copy_contents(save_dir, dest)
                else:
                    shutil.copytree(save_dir, dest)
            else:
                files = [f for f in save_dir.iterdir() if f.is_file()]
                if not files:
                    raise FileNotFoundError("No file found inside save folder.")
                if target.is_dir():
                    shutil.copy2(files[0], target / files[0].name)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(files[0], target)





    def mark_uploaded(self, folder_name, when=None):
        """Record that this save was successfully pushed to the cloud."""
        folder = self.user_saves_dir / folder_name
        cfg_path = folder / "config.json"
        if not cfg_path.exists():
            return
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            config["uploaded_at"] = when or _now_iso()
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except (OSError, json.JSONDecodeError):
            pass

    def resolve_thumbnail(self, stored):
        """Turn a config-stored thumbnail path into an absolute Path (or None)."""
        if not stored:
            return None
        p = Path(stored)
        if not p.is_absolute():
            p = self.base_dir / p
        return p if p.exists() else None

