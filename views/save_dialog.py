import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from PIL import Image, ImageTk

from views.utils import center_on_parent


PREVIEW_SIZE = 160   # px shown in the dialog


class SaveDialog(tk.Toplevel):
    """Reusable dialog for both importing and editing a save."""

    def __init__(self, parent, title="Import Save", save_data=None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.save_data = save_data or {}
        self.thumbnail_path = self.save_data.get("thumbnail") if save_data else None
        self.thumbnail_changed = False
        self._preview_photo = None

        self._build_ui()
        self._populate()

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        center_on_parent(self, parent)
        # Freeze the size after initial layout so picking an image
        # doesn't resize the dialog.
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        self.minsize(w, h)
        self.maxsize(w, h)

    # ------------------------------------------------------------------ #
    def _build_ui(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Title name:").grid(row=0, column=0, sticky="w", pady=6)
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(frame, textvariable=self.title_var, width=48)
        self.title_entry.grid(row=0, column=1, pady=6, sticky="ew")
        self.title_var.trace_add("write", self._on_title_change)

        ttk.Label(frame, text="Folder name:").grid(row=1, column=0, sticky="w", pady=6)
        self.folder_var = tk.StringVar()
        self.folder_entry = ttk.Entry(frame, textvariable=self.folder_var, width=48)
        self.folder_entry.grid(row=1, column=1, pady=6, sticky="ew")

        self.same_name_var = tk.BooleanVar(value=True)
        self.same_check = ttk.Checkbutton(
            frame,
            text="Folder name same as title",
            variable=self.same_name_var,
            command=self._on_same_toggle,
        )
        self.same_check.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Description:").grid(row=3, column=0, sticky="nw", pady=6)
        self.description_text = tk.Text(frame, width=48, height=4, wrap=tk.WORD)
        self.description_text.grid(row=3, column=1, pady=6, sticky="ew")

        ttk.Label(frame, text="Thumbnail:").grid(row=4, column=0, sticky="nw", pady=6)

        thumb_area = ttk.Frame(frame)
        thumb_area.grid(row=4, column=1, pady=6, sticky="ew")
        thumb_area.columnconfigure(0, weight=1)

        controls = ttk.Frame(thumb_area)
        controls.grid(row=0, column=0, sticky="ew")
        ttk.Button(controls, text="Browse...",
                   command=self._browse_thumb).pack(side=tk.LEFT)
        self.thumb_name_label = ttk.Label(controls, text="No image selected")
        self.thumb_name_label.pack(side=tk.LEFT, padx=10)

        # Reserve a fixed-size area so the preview never pushes the layout.
        self.preview_frame = tk.Frame(
            thumb_area, width=PREVIEW_SIZE, height=PREVIEW_SIZE,
            background="#f0f0f0", highlightthickness=1,
            highlightbackground="#cccccc",
        )
        self.preview_frame.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.preview_frame.grid_propagate(False)
        self.preview_frame.pack_propagate(False)

        self.preview_label = tk.Label(
            self.preview_frame, text="No preview",
            background="#f0f0f0", foreground="#888888",
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="OK", width=12,
                   command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", width=12,
                   command=self.destroy).pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------------ #
    def _populate(self):
        if self.save_data:
            title = self.save_data.get("title", "")
            folder = self.save_data.get("folder_name", "")
            self.same_name_var.set(title == folder)
            self.title_var.set(title)
            self.folder_var.set(folder)
            self._on_same_toggle()

            description = self.save_data.get("description", "")
            if description:
                self.description_text.insert("1.0", description)

            if self.thumbnail_path:
                p = Path(self.thumbnail_path)
                if not p.is_absolute():
                    p = Path(__file__).resolve().parent.parent / p
                if p.exists():
                    self.thumb_name_label.configure(text=p.name)
                    self._show_preview(str(p))
        else:
            self._on_same_toggle()

    def _on_title_change(self, *args):
        if self.same_name_var.get():
            self.folder_var.set(self.title_var.get())

    def _on_same_toggle(self):
        if self.same_name_var.get():
            self.folder_var.set(self.title_var.get())
            self.folder_entry.configure(state="disabled")
        else:
            self.folder_entry.configure(state="normal")

    # ------------------------------------------------------------------ #
    def _browse_thumb(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Select thumbnail image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.thumbnail_path = path
        self.thumbnail_changed = True
        self.thumb_name_label.configure(text=Path(path).name)
        self._show_preview(path)

    def _show_preview(self, path):
        try:
            with Image.open(path) as src:
                img = src.convert("RGBA")
            w, h = img.size
            size = min(w, h)
            left = (w - size) // 2
            top = (h - size) // 2
            img = img.crop((left, top, left + size, top + size))
            img = img.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
            self._preview_photo = ImageTk.PhotoImage(img)
            img.close()
            self.preview_label.configure(image=self._preview_photo, text="")
        except Exception as exc:
            self._preview_photo = None
            self.preview_label.configure(image="", text=f"Preview error")

    # ------------------------------------------------------------------ #
    @staticmethod
    def _sanitize_folder_name(name):
        bad = '<>:"/\\|?*'
        for ch in bad:
            name = name.replace(ch, "_")
        return name.strip().strip(".")

    def _on_ok(self):
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Error", "Title name is required.", parent=self)
            return

        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showerror("Error", "Folder name is required.", parent=self)
            return

        folder = self._sanitize_folder_name(folder)
        if not folder:
            messagebox.showerror("Error", "Folder name is invalid.", parent=self)
            return

        description = self.description_text.get("1.0", tk.END).strip()

        self.result = {
            "title": title,
            "folder_name": folder,
            "description": description,
            "thumbnail_path": self.thumbnail_path,
            "thumbnail_changed": self.thumbnail_changed,
        }
        self.destroy()