import tkinter as tk
from tkinter import ttk

from views.utils import center_on_parent


class ProviderPickerDialog(tk.Toplevel):
    def __init__(self, parent, title="Choose Cloud Provider"):
        super().__init__(parent)
        self.title(title)
        self.result = None

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        body = ttk.Frame(self, padding=20)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            body,
            text="Which cloud provider would you like to use?",
            font=("Arial", 11),
        ).pack(anchor="w", pady=(0, 12))

        self.choice_var = tk.StringVar(value="github")

        ttk.Radiobutton(body, text="GitHub Repository",
                        variable=self.choice_var, value="github"
                        ).pack(anchor="w", pady=2)
        ttk.Radiobutton(body, text="Google Drive",
                        variable=self.choice_var, value="gdrive"
                        ).pack(anchor="w", pady=2)

        self.remember_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            body, text="Remember my choice",
            variable=self.remember_var,
        ).pack(anchor="w", pady=(12, 0))

        btn_row = ttk.Frame(body)
        btn_row.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(btn_row, text="Cancel", width=10,
                   command=self._on_cancel).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_row, text="Continue", width=12,
                   command=self._on_ok).pack(side=tk.RIGHT, padx=4)

        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.bind("<Return>", lambda _e: self._on_ok())
        center_on_parent(self, parent)

    def _on_ok(self):
        self.result = {
            "provider": self.choice_var.get(),
            "remember": self.remember_var.get(),
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()