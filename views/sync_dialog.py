import threading
import tkinter as tk
from tkinter import ttk

from views.utils import center_on_parent


STATUS_LABELS = {
    "in_sync":     ("In sync",                "#2e7d32"),
    "modified":    ("Modified",                "#f57c00"),
    "local_only":  ("Only on this computer",   "#1565c0"),
    "remote_only": ("Only in cloud",           "#6a1b9a"),
}


def _fmt(iso):
    """'2026-10-01T14:23:07Z' -> '2026-10-01 14:23'  (empty if None)."""
    if not iso:
        return "—"
    try:
        return iso.replace("T", " ").replace("Z", "")[:16]
    except Exception:
        return iso

WINDOW_WIDTH = 820
WINDOW_HEIGHT = 520
TREE_ROWS = 10


class SyncDialog(tk.Toplevel):
    """Compare local saves against the cloud repo and choose a direction."""

    def __init__(self, parent, manager, on_finished=None):
        super().__init__(parent)
        self.title("Sync with Cloud")
        self.manager = manager
        self.on_finished = on_finished
        self._busy = False
        self._diffs = {}

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        center_on_parent(self, parent)

        # Lock the size so nothing shifts when the tree fills up.
        self.update_idletasks()
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.after(50, self._start_check)

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        # The outer frame fills the whole (fixed-size) window.
        outer = ttk.Frame(self, padding=15)
        outer.pack(fill=tk.BOTH, expand=True)

        # Give the tree row weight 1 so it stretches, and keep the button
        # row at weight 0 so it always sits at the bottom.
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(3, weight=1)   # row 3 = list_frame

        # ---- Header ------------------------------------------------ #
        ttk.Label(outer, text="Comparing local saves with cloud...",
                  font=("Arial", 11, "bold")).grid(
            row=0, column=0, sticky="w")

        self.status_label = ttk.Label(
            outer, text="Checking...", foreground="#333333",
            wraplength=WINDOW_WIDTH - 40, justify=tk.LEFT,
        )
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(6, 8))

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # ---- Differences list -------------------------------------- #
        list_frame = ttk.LabelFrame(outer, text="Differences")
        list_frame.grid(row=3, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            list_frame,
            columns=("save", "status", "local", "cloud"),
            show="headings",
            height=TREE_ROWS,
        )
        self.tree.heading("save",   text="Save")
        self.tree.heading("status", text="Status")
        self.tree.heading("local",  text="Local updated")
        self.tree.heading("cloud",  text="Cloud updated")
        self.tree.column("save",   width=250, anchor="w")
        self.tree.column("status", width=180, anchor="w")
        self.tree.column("local",  width=130, anchor="w")
        self.tree.column("cloud",  width=130, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        scroll = ttk.Scrollbar(list_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns", pady=4)

        # ---- Buttons ----------------------------------------------- #
        btn_row = ttk.Frame(outer)
        btn_row.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        self.upload_btn = ttk.Button(
            btn_row, text="Upload Local Changes", width=22,
            command=self._upload, state=tk.DISABLED,
        )
        self.upload_btn.pack(side=tk.LEFT, padx=4)

        self.download_btn = ttk.Button(
            btn_row, text="Download Cloud Changes", width=24,
            command=self._download, state=tk.DISABLED,
        )
        self.download_btn.pack(side=tk.LEFT, padx=4)

        self.close_btn = ttk.Button(
            btn_row, text="Close", width=12,
            command=self._on_close, state=tk.DISABLED,
        )
        self.close_btn.pack(side=tk.RIGHT, padx=4)

    # ------------------------------------------------------------------ #
    # Check phase
    # ------------------------------------------------------------------ #
    def _start_check(self):
        self.progress.start(12)
        self._busy = True
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self):
        try:
            provider = self.manager.get_provider()
            provider.detect()
            if not provider.is_ready():
                self.after(0, lambda: self._check_failed(provider.status_text()))
                return
            diffs = provider.compare_with_remote()
            self.after(0, lambda: self._check_done(diffs))
        except Exception as exc:
            self.after(0, lambda: self._check_failed(str(exc)))

    def _check_done(self, diffs):
        self._busy = False
        self.progress.stop()
        self._diffs = diffs
        self.close_btn.configure(state=tk.NORMAL)

        for row in self.tree.get_children():
            self.tree.delete(row)

        changed = 0
        for name in sorted(diffs):
            info = diffs[name]
            status = info["status"]
            label, color = STATUS_LABELS.get(status, (status, "#333333"))
            self.tree.insert(
                "", tk.END,
                values=(
                    name,
                    label,
                    _fmt(info.get("local_updated_at")),
                    _fmt(info.get("cloud_updated_at")),
                ),
                tags=(status,),
            )
            self.tree.tag_configure(status, foreground=color)
            if status != "in_sync":
                changed += 1

        if changed == 0:
            self.status_label.configure(
                text="Everything is in sync. Nothing to do.",
                foreground="#2e7d32",
            )
            self.upload_btn.configure(state=tk.DISABLED)
            self.download_btn.configure(state=tk.DISABLED)
        else:
            self.status_label.configure(
                text=(f"{changed} save(s) differ. Choose a direction:\n"
                      "• Upload Local Changes — overwrite cloud with this PC's saves.\n"
                      "• Download Cloud Changes — overwrite this PC's saves with the cloud."),
                foreground="#333333",
            )
            self.upload_btn.configure(state=tk.NORMAL)
            self.download_btn.configure(state=tk.NORMAL)

    def _check_failed(self, err):
        self._busy = False
        self.progress.stop()
        self.close_btn.configure(state=tk.NORMAL)
        self.status_label.configure(text=f"Error: {err}", foreground="red")

    # ------------------------------------------------------------------ #
    # Action phase
    # ------------------------------------------------------------------ #
    def _upload(self):
        self._run_action("upload")

    def _download(self):
        self._run_action("download")

    def _run_action(self, action):
        if self._busy:
            return
        self._busy = True
        self.progress.start(12)
        self.status_label.configure(text="Working...", foreground="#333333")
        self.upload_btn.configure(state=tk.DISABLED)
        self.download_btn.configure(state=tk.DISABLED)
        self.close_btn.configure(state=tk.DISABLED)
        threading.Thread(
            target=self._action_worker, args=(action,), daemon=True
        ).start()

    def _action_worker(self, action):
        try:
            provider = self.manager.get_provider()
            if action == "upload":
                provider.upload_all(progress_cb=self._report)
            else:
                provider.pull_all(progress_cb=self._report)
            self.after(0, lambda: self._action_done(action))
        except Exception as exc:
            self.after(0, lambda: self._check_failed(str(exc)))

    def _report(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _action_done(self, action):
        self._busy = False
        self.progress.stop()
        word = "Upload" if action == "upload" else "Download"
        self.status_label.configure(
            text=f"{word} complete.", foreground="#2e7d32")
        self.close_btn.configure(state=tk.NORMAL)
        if self.on_finished:
            self.on_finished()

    # ------------------------------------------------------------------ #
    def _on_close(self):
        if self._busy:
            return  # keep the user from closing mid-operation
        self.destroy()