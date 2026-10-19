import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from views.confirm_dialog import ConfirmDialog
from views.utils import center_on_parent


CLOUD_OPTIONS = [
    ("ask", "Ask me every time"),
    ("gdrive", "Google Drive"),
    ("github", "GitHub Repository"),
]


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.settings = controller.settings

        self.title("Settings")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._build_ui()
        center_on_parent(self, parent)

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        body = ttk.Frame(self, padding=15)
        body.pack(fill=tk.BOTH, expand=True)

        # ---- Save directory ----
        dir_frame = ttk.LabelFrame(body, text="Save directory")
        dir_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(
            dir_frame,
            text=("Where 'user saves' and 'thumbnails' live. "
                  "Changing this moves existing files."),
            wraplength=440, foreground="#555555",
        ).pack(anchor="w", padx=8, pady=(6, 4))

        row = ttk.Frame(dir_frame)
        row.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.dir_var = tk.StringVar(value=str(self.settings.get_save_root()))
        self.dir_entry = ttk.Entry(row, textvariable=self.dir_var, width=44)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="Browse...", width=10,
                   command=self._browse).pack(side=tk.LEFT, padx=(6, 0))

        self.apply_dir_btn = ttk.Button(
            dir_frame, text="Apply directory",
            command=self._apply_dir,
        )
        self.apply_dir_btn.pack(anchor="e", padx=8, pady=(0, 8))

        # ---- Cloud provider ----
        cloud_frame = ttk.LabelFrame(body, text="Cloud provider")
        cloud_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(
            cloud_frame,
            text="Used by 'Upload to Cloud' and 'Sync with Cloud'.",
            foreground="#555555",
        ).pack(anchor="w", padx=8, pady=(6, 4))

        self.cloud_var = tk.StringVar(value=self.settings.get_cloud_provider())
        cloud_combo = ttk.Combobox(
            cloud_frame, state="readonly",
            values=[label for _v, label in CLOUD_OPTIONS],
            width=32,
        )
        current_label = dict((v, label) for v, label in CLOUD_OPTIONS)
        cloud_combo.set(current_label.get(self.cloud_var.get(), "Ask me every time"))
        cloud_combo.pack(anchor="w", padx=8, pady=(0, 8))
        cloud_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._on_cloud_combo(cloud_combo.get()),
        )
        self._cloud_combo = cloud_combo

        # ---- Footer ----
        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Close", width=10,
                   command=self.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    def _browse(self):
        picked = filedialog.askdirectory(
            parent=self, title="Select save root directory",
            initialdir=self.dir_var.get(),
        )
        if picked:
            self.dir_var.set(picked)

    def _apply_dir(self):
        new = self.dir_var.get().strip()
        if not new:
            messagebox.showerror("Invalid path", "Directory cannot be empty.",
                                 parent=self)
            return

        target = Path(new).resolve()
        current = self.settings.get_save_root().resolve()
        if target == current:
            messagebox.showinfo("No change",
                                "The directory is already in use.",
                                parent=self)
            return

        warn = ConfirmDialog(
            self,
            title="Move save data?",
            message=(
                "Move existing 'user saves' and 'thumbnails' to:\n\n"
                f"{target}\n\n"
                "Existing files in that folder will not be overwritten; "
                "if 'user saves' or 'thumbnails' already exist there, "
                "the move is refused.\n\n"
                "Continue?"
            ),
            yes_text="Move", no_text="Cancel",
        )
        self.wait_window(warn)
        if not warn.result:
            return

        try:
            self.controller.move_save_root(target)
        except Exception as exc:
            messagebox.showerror("Move failed", str(exc), parent=self)
            return

        messagebox.showinfo("Done", "Save directory updated.", parent=self)
        self.dir_var.set(str(target))

    def _on_cloud_combo(self, selected_label):
        for value, label in CLOUD_OPTIONS:
            if label == selected_label:
                self.settings.set_cloud_provider(value)
                self.controller.on_cloud_provider_setting_changed(value)
                return