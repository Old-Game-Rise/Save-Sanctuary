import threading
import tkinter as tk
from tkinter import ttk

from views.utils import center_on_parent


class CloudUploadDialog(tk.Toplevel):
    """Progress dialog for a cloud upload. Runs the actual upload in a thread."""

    def __init__(self, parent, manager, saves_count):
        super().__init__(parent)
        self.title("Upload to Cloud")
        self.manager = manager
        self.saves_count = saves_count
        self._done = False

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        center_on_parent(self, parent)

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            frame,
            text=f"Backing up {self.saves_count} save(s) to GitHub",
            font=("Arial", 11, "bold"),
        )
        header.pack(anchor="w")

        status_row = ttk.Frame(frame)
        status_row.pack(fill=tk.X, pady=(8, 6))
        ttk.Label(status_row, text="Status:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_row, text="Preparing...",
                                      foreground="#333333")
        self.status_label.pack(side=tk.LEFT, padx=(6, 0))

        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=460)
        self.progress.pack(fill=tk.X, pady=(0, 10))

        log_frame = ttk.LabelFrame(frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(
            log_frame, width=66, height=11, wrap=tk.WORD,
            state=tk.DISABLED, background="#f7f7f7",
            borderwidth=0, highlightthickness=0,
        )
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(12, 0))
        self.close_btn = ttk.Button(
            btn_row, text="Close", width=12,
            command=self._on_close, state=tk.DISABLED,
        )
        self.close_btn.pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    def start(self):
        self.progress.start(12)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            url = self.manager.upload_all(progress_cb=self._report)
            self.after(0, lambda: self._on_success(url))
        except Exception as exc:
            self.after(0, lambda: self._on_error(str(exc)))

    def _report(self, msg):
        self.after(0, lambda: self._log(msg))

    def _log(self, msg):
        self.status_label.configure(text=msg)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"• {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------ #
    def _on_success(self, url):
        self._done = True
        self.progress.stop()
        self._log(f"Repository: {url}")
        self.status_label.configure(text="Backup complete.", foreground="green")
        self.close_btn.configure(state=tk.NORMAL)

    def _on_error(self, err):
        self._done = True
        self.progress.stop()
        self._log(f"ERROR: {err}")
        self.status_label.configure(text="Backup failed.", foreground="red")
        self.close_btn.configure(state=tk.NORMAL)

    def _on_close(self):
        if not self._done:
            return  # keep the user from closing mid-upload
        self.destroy()