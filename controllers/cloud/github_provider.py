import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from controllers.cloud.base import CloudProvider


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class GitError(Exception):
    """Raised when a git/gh command fails."""


def _run(args, cwd=None, check=True, timeout=None):
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        raise GitError(f"Command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        raise GitError(f"Command timed out: {' '.join(args)}")

    if check and result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        raise GitError(f"Command failed ({result.returncode}): {' '.join(args)}\n{msg}")
    return result


# ------------------------------------------------------------------ #
# Hashing helpers (used to compare local vs remote)
# ------------------------------------------------------------------ #
def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_file_normalized(path):
    """For config.json, ignore machine-specific and timestamp fields."""
    if path.name == "config.json":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["original_path"] = "<original_path>"
            data.pop("updated_at", None)
            data.pop("uploaded_at", None)
            normalized = json.dumps(data, indent=4, sort_keys=True).encode("utf-8")
            return hashlib.sha256(normalized).hexdigest()
        except (OSError, json.JSONDecodeError):
            pass
    return _hash_file(path)


def _hash_tree(path):
    """Return {relpath: sha} for a file or dir. Empty dict if path missing."""
    path = Path(path)
    if not path.exists():
        return {}
    if path.is_file():
        return {"": _hash_file_normalized(path)}
    result = {}
    for root, _dirs, files in os.walk(path):
        for f in files:
            full = Path(root) / f
            rel = str(full.relative_to(path)).replace("\\", "/")
            result[rel] = _hash_file_normalized(full)
    return result


def _combine_hashes(*parts):
    h = hashlib.sha256()
    for p in parts:
        for k in sorted(p):
            h.update(k.encode("utf-8"))
            h.update(b"\0")
            h.update(p[k].encode("utf-8"))
            h.update(b"\0")
    return h.hexdigest()


# ------------------------------------------------------------------ #
# Auth detection
# ------------------------------------------------------------------ #
def detect_auth():
    info = {
        "git": False, "gh": False, "gh_user": None,
        "credential_user": None, "token": None,
    }

    try:
        _run(["git", "--version"])
        info["git"] = True
    except GitError:
        return info

    try:
        r = _run(["gh", "auth", "status"], check=False, timeout=15)
        if r.returncode == 0:
            info["gh"] = True
            combined = (r.stdout or "") + (r.stderr or "")
            m = re.search(r"account\s+(\S+)", combined)
            if m:
                info["gh_user"] = m.group(1)
    except GitError:
        pass

    try:
        r = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        if r.returncode == 0:
            for line in (r.stdout or "").splitlines():
                if line.startswith("username="):
                    info["credential_user"] = line.split("=", 1)[1]
                elif line.startswith("password="):
                    info["token"] = line.split("=", 1)[1]
    except Exception:
        pass

    return info


class GitHubProvider(CloudProvider):
    NAME = "GitHub"

    def __init__(self, app_dir, repo_name="game-save-manager-backups"):
        self.app_dir = Path(app_dir).resolve()
        self.user_saves_dir = self.app_dir / "user saves"
        self.local_thumbs_dir = self.app_dir / "thumbnails"
        self.work_dir = self.app_dir / "cloud_backup"
        self.repo_name = repo_name
        self.auth = None

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #
    def detect(self):
        self.auth = detect_auth()
        return self.auth

    def is_ready(self):
        if self.auth is None:
            self.detect()
        return bool(self.auth.get("git")) and bool(
            self.auth.get("gh") or self.auth.get("token")
        )

    def status_text(self):
        if self.auth is None:
            self.detect()
        if not self.auth.get("git"):
            return ("Git is not installed.\n\n"
                    "Please install Git from https://git-scm.com/downloads and try again.")
        if self.auth.get("gh"):
            user = self.auth.get("gh_user") or "?"
            return f"Ready — signed in to GitHub as '{user}' via GitHub CLI."
        if self.auth.get("token"):
            user = self.auth.get("credential_user") or "?"
            return f"Ready — using saved Git credentials for '{user}'."
        return ("Not signed in to GitHub.\n\n"
                "Either:\n"
                "  • Install GitHub CLI (https://cli.github.com) and run 'gh auth login'\n"
                "  • Or sign in to GitHub once with your Git client "
                "(e.g. 'git push' to any GitHub repo) so Credential Manager stores a token.")

    # ------------------------------------------------------------------ #
    # Remote repo
    # ------------------------------------------------------------------ #
    def _ensure_remote_repo(self, progress_cb=None):
        report = progress_cb or (lambda _m: None)

        if self.auth.get("gh"):
            r = _run(["gh", "repo", "view", self.repo_name,
                      "--json", "url"], check=False, timeout=30)
            if r.returncode != 0:
                report(f"Creating GitHub repository '{self.repo_name}'...")
                _run(["gh", "repo", "create", self.repo_name,
                      "--private",
                      "--description",
                      "Game save backups (created by SAVE SANCTUARY)"],
                     timeout=60)
            r = _run(["gh", "repo", "view", self.repo_name,
                      "--json", "url"], timeout=30)
            return json.loads(r.stdout)["url"]

        token = self.auth.get("token")
        if not token:
            raise GitError("No GitHub authentication available.")

        user = self._api_get("https://api.github.com/user", token)
        login = user["login"]
        repo_url = f"https://api.github.com/repos/{login}/{self.repo_name}"

        try:
            self._api_get(repo_url, token)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                report(f"Creating GitHub repository '{self.repo_name}'...")
                self._api_post("https://api.github.com/user/repos", token, {
                    "name": self.repo_name,
                    "private": True,
                    "description": "Game save backups (created by Game Save Manager)",
                })
            else:
                raise GitError(f"GitHub API error: {e.code} {e.reason}")

        return f"https://github.com/{login}/{self.repo_name}.git"

    # ------------------------------------------------------------------ #
    # Local repo
    # ------------------------------------------------------------------ #
    def _ensure_local_repo(self, remote_url, progress_cb=None):
        report = progress_cb or (lambda _m: None)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        if not (self.work_dir / ".git").exists():
            report("Initializing local backup repository...")
            r = _run(["git", "init", "-b", "main"],
                     cwd=self.work_dir, check=False)
            if r.returncode != 0:
                _run(["git", "init"], cwd=self.work_dir)
                _run(["git", "symbolic-ref", "HEAD", "refs/heads/main"],
                     cwd=self.work_dir)
            _run(["git", "config", "user.email", "gamesavemanager@localhost"],
                 cwd=self.work_dir)
            _run(["git", "config", "user.name", "Game Save Manager"],
                 cwd=self.work_dir)

        r = _run(["git", "remote", "get-url", "origin"],
                 cwd=self.work_dir, check=False)
        if r.returncode != 0:
            _run(["git", "remote", "add", "origin", remote_url],
                 cwd=self.work_dir)
        elif r.stdout.strip() != remote_url:
            _run(["git", "remote", "set-url", "origin", remote_url],
                 cwd=self.work_dir)

    def _fetch_and_reset(self, progress_cb=None):
        report = progress_cb or (lambda _m: None)
        if not (self.work_dir / ".git").exists():
            return

        report("Fetching from GitHub...")
        r = _run(["git", "fetch", "origin"],
                 cwd=self.work_dir, check=False, timeout=180)
        if r.returncode != 0:
            msg = (r.stderr or "").strip()
            if "couldn't find remote ref" in msg.lower() or "no such remote" in msg.lower():
                return
            raise GitError(f"Fetch failed:\n{msg}")

        r = _run(["git", "rev-parse", "--verify", "origin/main"],
                 cwd=self.work_dir, check=False)
        if r.returncode != 0:
            # Remote has no commits yet
            return

        report("Resetting working copy to remote state...")
        _run(["git", "reset", "--hard", "origin/main"], cwd=self.work_dir)

    # ------------------------------------------------------------------ #
    # Push (mirror local → cloud_backup → commit → push)
    # ------------------------------------------------------------------ #
    def _sync_saves_to_repo(self):
        # --- saves ---
        dest_root = self.work_dir / "saves"
        dest_root.mkdir(parents=True, exist_ok=True)

        current = set()
        if self.user_saves_dir.exists():
            current = {p.name for p in self.user_saves_dir.iterdir() if p.is_dir()}

        for name in current:
            src = self.user_saves_dir / name
            dst = dest_root / name
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)

        for item in list(dest_root.iterdir()):
            if item.name not in current:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink()

        # --- thumbnails ---
        dest_thumbs = self.work_dir / "thumbnails"
        dest_thumbs.mkdir(parents=True, exist_ok=True)

        if self.local_thumbs_dir.exists():
            for f in self.local_thumbs_dir.iterdir():
                if f.is_file():
                    shutil.copy2(f, dest_thumbs / f.name)

        for f in list(dest_thumbs.iterdir()):
            if f.is_file() and f.stem not in current:
                f.unlink()

    def upload_all(self, progress_cb=None):
        report = progress_cb or (lambda _m: None)
        if not self.is_ready():
            raise GitError(self.status_text())

        report("Checking remote repository...")
        remote_url = self._ensure_remote_repo(progress_cb)
        self._ensure_local_repo(remote_url, progress_cb)

        # Bring local repo up to date with remote so we don't fight history
        try:
            self._fetch_and_reset(progress_cb)
        except GitError:
            pass  # fresh repo, nothing to fetch

        report("Syncing saves into working copy...")
        self._sync_saves_to_repo()

        report("Staging changes...")
        _run(["git", "add", "-A"], cwd=self.work_dir)

        r = _run(["git", "status", "--porcelain"],
                 cwd=self.work_dir, timeout=30)
        if r.stdout.strip():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report("Committing changes...")
            _run(["git", "commit", "-m", f"Backup {timestamp}"],
                 cwd=self.work_dir)
        else:
            report("No changes since last backup.")

        r = _run(["git", "symbolic-ref", "--short", "HEAD"],
                 cwd=self.work_dir, check=False)
        branch = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "main"

        report(f"Pushing to GitHub ({branch})...")
        r = _run(["git", "push", "-u", "origin", branch],
                 cwd=self.work_dir, check=False, timeout=300)
        if r.returncode != 0:
            raise GitError(f"Push failed:\n{(r.stderr or r.stdout or '').strip()}")

        # Stamp local saves as uploaded. Do this through the model so the
        # timestamps survive next time we sync.
        from models.save_model import SaveModel
        model = SaveModel(self.app_dir)
        for name in [p.name for p in self.user_saves_dir.iterdir() if p.is_dir()]:
            model.mark_uploaded(name)

        report("Backup complete.")
        return remote_url

    # ------------------------------------------------------------------ #
    # Pull (cloud_backup → user saves + thumbnails)
    # ------------------------------------------------------------------ #
    def pull_all(self, progress_cb=None):
        report = progress_cb or (lambda _m: None)
        if not self.is_ready():
            raise GitError(self.status_text())

        report("Checking remote repository...")
        remote_url = self._ensure_remote_repo(progress_cb)
        self._ensure_local_repo(remote_url, progress_cb)
        self._fetch_and_reset(progress_cb)

        remote_saves = self.work_dir / "saves"
        remote_thumbs = self.work_dir / "thumbnails"

        # 1) Restore thumbnails FIRST so config's relative paths resolve.
        if remote_thumbs.exists():
            report("Restoring thumbnails...")
            self.local_thumbs_dir.mkdir(parents=True, exist_ok=True)
            for f in remote_thumbs.iterdir():
                if f.is_file():
                    shutil.copy2(f, self.local_thumbs_dir / f.name)

        # 2) Restore saves.
        if remote_saves.exists():
            report("Restoring saves...")
            for name in [p.name for p in remote_saves.iterdir() if p.is_dir()]:
                src = remote_saves / name
                dst = self.user_saves_dir / name

                cloud_updated, cloud_uploaded = _read_timestamps(
                    src / "config.json")

                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)

                # Only timestamps need local adjustment.
                cfg_path = dst / "config.json"
                if cfg_path.exists():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        if cloud_updated:
                            cfg["updated_at"] = cloud_updated
                        cfg["uploaded_at"] = cloud_uploaded or cloud_updated
                        with open(cfg_path, "w", encoding="utf-8") as f:
                            json.dump(cfg, f, indent=4)
                    except (OSError, json.JSONDecodeError):
                        pass

        report("Download complete.")
        return remote_url

    # ------------------------------------------------------------------ #
    # Compare
    # ------------------------------------------------------------------ #
    def compare_with_remote(self, progress_cb=None):
        """
        Return {save_name: {
            'status':  'in_sync' | 'modified' | 'local_only' | 'remote_only',
            'local_updated_at':  <iso or None>,
            'local_uploaded_at': <iso or None>,
            'cloud_updated_at':  <iso or None>,
            'cloud_uploaded_at': <iso or None>,
        }}
        """
        report = progress_cb or (lambda _m: None)
        if not self.is_ready():
            raise GitError(self.status_text())

        if not (self.work_dir / ".git").exists():
            try:
                remote_url = self._ensure_remote_repo(progress_cb)
                self._ensure_local_repo(remote_url, progress_cb)
            except GitError:
                pass

        self._fetch_and_reset(progress_cb)

        local_saves = self.user_saves_dir
        remote_saves = self.work_dir / "saves"

        local_names = {p.name for p in local_saves.iterdir() if p.is_dir()} \
            if local_saves.exists() else set()
        remote_names = {p.name for p in remote_saves.iterdir() if p.is_dir()} \
            if remote_saves.exists() else set()

        report("Comparing saves...")
        result = {}
        for name in local_names | remote_names:
            local_hash = None
            remote_hash = None
            local_updated = local_uploaded = None
            cloud_updated = cloud_uploaded = None

            if name in local_names:
                local_dir = local_saves / name
                local_hash = _combine_hashes(
                    _hash_tree(local_dir),
                    _hash_tree(self.local_thumbs_dir / f"{name}.png"),
                )
                local_updated, local_uploaded = _read_timestamps(
                    local_dir / "config.json")

            if name in remote_names:
                remote_dir = remote_saves / name
                remote_hash = _combine_hashes(
                    _hash_tree(remote_dir),
                    _hash_tree(self.work_dir / "thumbnails" / f"{name}.png"),
                )
                cloud_updated, cloud_uploaded = _read_timestamps(
                    remote_dir / "config.json")

            if local_hash and remote_hash:
                status = "in_sync" if local_hash == remote_hash else "modified"
            elif local_hash:
                status = "local_only"
            else:
                status = "remote_only"

            result[name] = {
                "status": status,
                "local_updated_at": local_updated,
                "local_uploaded_at": local_uploaded,
                "cloud_updated_at": cloud_updated,
                "cloud_uploaded_at": cloud_uploaded,
            }

        return result


    # ------------------------------------------------------------------ #
    # Tiny API helpers (only used when `gh` is missing)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _api_get(url, token):
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "GameSaveManager",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _api_post(url, token, payload):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "GameSaveManager",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

# ------------------------------------------------------------------ #
# Timestamp helpers
# ------------------------------------------------------------------ #
def _read_timestamps(config_path):
    """Return (updated_at, uploaded_at) from a config.json, or (None, None)."""
    p = Path(config_path)
    if not p.exists():
        return (None, None)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("updated_at"), data.get("uploaded_at"))
    except (OSError, json.JSONDecodeError):
        return (None, None)


def _read_timestamps_from_dict(data):
    """Same as _read_timestamps but takes an already-parsed dict."""
    if not isinstance(data, dict):
        return (None, None)
    return (data.get("updated_at"), data.get("uploaded_at"))