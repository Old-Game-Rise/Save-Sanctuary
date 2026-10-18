import json
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import ttk

from views.utils import center_on_parent

import os
from pathlib import Path


def _steam_drm_sources():
    """Return [(label, root_path), ...] — every place we look for DRM saves."""
    sources = [
        ("RUNE",      Path(r"C:\Users\Public\Documents\Steam\RUNE")),
        ("CODEX",     Path(r"C:\Users\Public\Documents\Steam\CODEX")),
        ("OnlineFix", Path(r"C:\Users\Public\Documents\OnlineFix")),
    ]

    # Goldberg lives under %APPDATA%\Goldberg SteamEmu Saves on Windows.
    appdata = os.environ.get("APPDATA")
    if appdata:
        sources.append((
            "Goldberg",
            Path(appdata) / "Goldberg SteamEmu Saves",
        ))

    return sources


# Subfolders to ignore inside a source root (they're not game save folders).
IGNORED_SUBFOLDERS = {"settings"}

WINDOW_WIDTH = 640
WINDOW_HEIGHT = 540
TREE_ROWS = 12


# ------------------------------------------------------------------ #
# Name resolution (with on-disk cache)
# ------------------------------------------------------------------ #
def _cache_path(app_dir):
    return Path(app_dir) / "steam_appid_cache.json"


def _load_cache(app_dir):
    p = _cache_path(app_dir)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(app_dir, cache):
    try:
        with open(_cache_path(app_dir), "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
    except OSError:
        pass


def _resolve_appid_name(appid):
    """Return the game name for an AppID, or None if it can't be resolved."""
    url = (
        "https://store.steampowered.com/api/appdetails"
        f"?appids={appid}&filters=basic&l=english"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None

    entry = data.get(str(appid), {})
    if entry.get("success") and entry.get("data"):
        return entry["data"].get("name")
    return None


# ------------------------------------------------------------------ #
# Dialog
# ------------------------------------------------------------------ #
class SteamPresetDialog(tk.Toplevel):
    """
    Scan RUNE / CODEX DRM-free save folders and let the user pick one.

    After the dialog closes, `result` is either:
        - None                                   (cancelled / nothing picked)
        - {"appid": "761600",
           "title": "Onimusha: Warlords",        (or None if unresolved)
           "folder_path": "C:\\...\\RUNE\\761600"}
    """

    def __init__(self, parent, app_dir):
        super().__init__(parent)
        self.title("Import DRM-free Steam Save")
        self.app_dir = Path(app_dir)
        self.result = None
        self._busy = False
        self._rows = {}          # iid -> (appid, name, folder_path)
        self._cache = _load_cache(self.app_dir)
        self._cache_dirty = False

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        center_on_parent(self, parent)
        self.update_idletasks()
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.after(50, self._start_scan)

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        outer = ttk.Frame(self, padding=15)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)

        ttk.Label(
            outer, text="DRM-free Steam saves",
            font=("Arial", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.status_label = ttk.Label(
            outer, text="Looking for RUNE / CODEX folders...",
            foreground="#333333", wraplength=WINDOW_WIDTH - 40,
            justify=tk.LEFT,
        )
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(6, 8))

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        list_frame = ttk.LabelFrame(outer, text="Games found")
        list_frame.grid(row=3, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("game", "appid", "source"),
            show="headings",
            height=TREE_ROWS,
        )
        self.tree.heading("game", text="Game")
        self.tree.heading("appid", text="AppID")
        self.tree.heading("source", text="Source")
        self.tree.column("game", width=350, anchor="w")
        self.tree.column("appid", width=90, anchor="w")
        self.tree.column("source", width=130, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.tree.bind("<Double-1>", lambda _e: self._on_use())

        scroll = ttk.Scrollbar(list_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns", pady=4)

        btn_row = ttk.Frame(outer)
        btn_row.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        self.use_btn = ttk.Button(
            btn_row, text="Use Selected", width=16,
            command=self._on_use, state=tk.DISABLED,
        )
        self.use_btn.pack(side=tk.LEFT, padx=4)

        self.rescan_btn = ttk.Button(
            btn_row, text="Rescan", width=10,
            command=self._on_rescan,
        )
        self.rescan_btn.pack(side=tk.LEFT, padx=4)

        ttk.Button(
            btn_row, text="Cancel", width=12,
            command=self._on_close,
        ).pack(side=tk.RIGHT, padx=4)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    # ------------------------------------------------------------------ #
    # Scan
    # ------------------------------------------------------------------ #
    def _start_scan(self):
        self.progress.start(12)
        self._busy = True
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            found = []
            for source_name, root in _steam_drm_sources():
                if not root.exists() or not root.is_dir():
                    continue
                for folder in sorted(root.iterdir()):
                    if not folder.is_dir():
                        continue

                    # Skip non-numeric folders and known non-game folders.
                    if folder.name.lower() in IGNORED_SUBFOLDERS:
                        continue
                    if not folder.name.isdigit():
                        continue

                    appid = folder.name
                    cached = self._cache.get(appid)
                    if cached is not None:
                        name = cached
                    else:
                        self._report(f"Resolving {appid}...")
                        name = _resolve_appid_name(appid)
                        self._cache[appid] = name
                        self._cache_dirty = True

                    found.append({
                        "appid": appid,
                        "title": name,
                        "source": source_name,
                        "folder_path": str(folder.resolve()),
                    })

            found.sort(key=lambda r: (
                r["title"] is None,
                (r["title"] or "").lower(),
                r["appid"],
            ))
            self.after(0, lambda: self._on_scan_done(found))
        except Exception as exc:
            self.after(0, lambda: self._on_scan_failed(str(exc)))

    def _report(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _on_scan_done(self, found):
        self._busy = False
        self.progress.stop()

        if self._cache_dirty:
            _save_cache(self.app_dir, self._cache)
            self._cache_dirty = False

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._rows.clear()

        if not found:
            self.status_label.configure(
                text=("No DRM-free Steam saves were found. Looked in:\n"
                      "  • C:\\Users\\Public\\Documents\\Steam\\RUNE\n"
                      "  • C:\\Users\\Public\\Documents\\Steam\\CODEX\n"
                      "  • C:\\Users\\Public\\Documents\\OnlineFix\n"
                      "  • %APPDATA%\\Goldberg SteamEmu Saves\n\n"
                      "If none of these exist on your PC, use the normal "
                      "'Single File' or 'Folder' import instead."),
                foreground="#a04000",
            )
            return

        for entry in found:
            display_title = entry["title"] or "(unknown — double-click to view)"
            iid = self.tree.insert(
                "", tk.END,
                values=(display_title, entry["appid"], entry["source"]),
            )
            self._rows[iid] = entry

        self.status_label.configure(
            text=(f"Found {len(found)} game(s). "
                  "Select one and click 'Use Selected'."),
            foreground="#333333",
        )

    def _on_scan_failed(self, err):
        self._busy = False
        self.progress.stop()
        self.status_label.configure(text=f"Scan error: {err}", foreground="red")

    def _on_rescan(self):
        if self._busy:
            return
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._rows.clear()
        self.use_btn.configure(state=tk.DISABLED)
        self.status_label.configure(
            text="Rescanning DRM-free save folders...",
            foreground="#333333",
        )
        self._start_scan()

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #
    def _on_tree_select(self, _event=None):
        selection = self.tree.selection()
        self.use_btn.configure(
            state=tk.NORMAL if selection else tk.DISABLED)

    def _on_use(self):
        if self._busy:
            return
        selection = self.tree.selection()
        if not selection:
            return
        entry = self._rows.get(selection[0])
        if not entry:
            return
        self.result = {
            "appid": entry["appid"],
            "title": entry["title"],   # may be None
            "folder_path": entry["folder_path"],
        }
        self.destroy()

    # ------------------------------------------------------------------ #
    def _on_close(self):
        if self._busy:
            return  # let the scan finish rather than abandon it
        self.destroy()