import tkinter as tk
from tkinter import ttk

from views.utils import center_on_parent


class ConfirmDialog(tk.Toplevel):
    """
    Generic Yes/No modal.

    If `danger=True`, the confirm button is drawn in red (used for Delete).
    """

    def __init__(self, parent, title, message,
                 yes_text="Yes", no_text="No",
                 danger=False):
        super().__init__(parent)
        self.title(title)
        self.result = False

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        body = ttk.Frame(self, padding=20)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text=message, wraplength=420,
                  justify=tk.LEFT, font=("Arial", 11)).pack(pady=(0, 20))

        btn_frame = ttk.Frame(body)
        btn_frame.pack()

        ttk.Button(btn_frame, text=no_text, width=12,
                   command=self._on_no).pack(side=tk.LEFT, padx=6)

        if danger:
            confirm_btn = tk.Button(
                btn_frame, text=yes_text, width=12,
                fg="red", activeforeground="red",
                command=self._on_yes,
            )
        else:
            confirm_btn = ttk.Button(btn_frame, text=yes_text, width=12,
                                     command=self._on_yes)
        confirm_btn.pack(side=tk.LEFT, padx=6)

        self.protocol("WM_DELETE_WINDOW", self._on_no)
        self.bind("<Escape>", lambda _e: self._on_no())
        self.bind("<Return>", lambda _e: self._on_yes())

        center_on_parent(self, parent)
        self.focus_set()

    def _on_no(self):
        self.result = False
        self.destroy()

    def _on_yes(self):
        self.result = True
        self.destroy()

class ConfirmDeleteDialog(ConfirmDialog):
    def __init__(self, parent, title, message):
        super().__init__(parent, title, message,
                         yes_text="Delete", no_text="No", danger=True)