import tkinter as tk
from tkinter import ttk

from views.utils import center_on_parent


class ConfirmDeleteDialog(tk.Toplevel):
    """A modal 'No / Delete' confirmation dialog with a red Delete button."""

    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.title(title)
        self.result = False

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        body = ttk.Frame(self, padding=20)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text=message, wraplength=380,
                  justify=tk.LEFT, font=("Arial", 11)).pack(pady=(0, 20))

        btn_frame = ttk.Frame(body)
        btn_frame.pack()

        no_btn = ttk.Button(btn_frame, text="No", width=12,
                            command=self._on_no)
        no_btn.pack(side=tk.LEFT, padx=6)

        # Red "Delete" button (tk.Button because ttk styling for fg is limited)
        delete_btn = tk.Button(
            btn_frame,
            text="Delete",
            width=12,
            fg="red",
            activeforeground="red",
            command=self._on_delete,
        )
        delete_btn.pack(side=tk.LEFT, padx=6)

        self.protocol("WM_DELETE_WINDOW", self._on_no)
        self.bind("<Escape>", lambda e: self._on_no())
        self.bind("<Return>", lambda e: self._on_delete())

        center_on_parent(self, parent)
        self.focus_set()

    def _on_no(self):
        self.result = False
        self.destroy()

    def _on_delete(self):
        self.result = True
        self.destroy()