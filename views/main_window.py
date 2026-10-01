import tkinter as tk
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageTk
import webbrowser
from version import (
    APP_NAME, APP_VERSION,
    APP_AUTHOR, APP_AUTHOR_URL, APP_REPO_URL,
)


class MainWindow:
    """Left = scrollable list of saves. Right = action buttons + menu bar."""

    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self._thumb_cache = {}
        self._cards = {}
        self._selected = None
        self._saves_by_folder = {}

        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1040x660")
        self.root.minsize(860, 520)

        self._build_menu()
        self._build_ui()

    # ------------------------------------------------------------------ #
    # Menu bar
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import Save...",
                              command=self.controller.import_save)
        file_menu.add_command(label="Refresh", command=self.controller.refresh)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        save_menu = tk.Menu(menubar, tearoff=0)
        save_menu.add_command(label="Renew",
                              command=self.controller.renew_selected)
        save_menu.add_command(label="Edit...",
                              command=self.controller.edit_selected)
        save_menu.add_command(label="Export",
                              command=self.controller.export_selected)
        save_menu.add_command(label="Export Manually...",
                              command=self.controller.export_selected_manually)
        save_menu.add_separator()
        save_menu.add_command(label="Sync with Cloud...",
                              command=self.controller.sync_with_cloud)
        save_menu.add_command(label="Upload to Cloud",
                              command=self.controller.upload_selected_to_cloud)
        save_menu.add_command(label="Upload to Cloud",
                              command=self.controller.upload_selected_to_cloud)
        save_menu.add_separator()
        save_menu.add_command(label="Delete...",
                              command=self.controller.delete_selected)
        menubar.add_cascade(label="Save", menu=save_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _show_about(self):
        from tkinter import ttk
        import tkinter as tk

        dialog = tk.Toplevel(self.root)
        dialog.title(f"About {APP_NAME}")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # --- Title ---
        ttk.Label(
            frame, text=APP_NAME,
            font=("Arial", 16, "bold"),
        ).pack(anchor="center")

        ttk.Label(
            frame, text=f"Version {APP_VERSION}",
            foreground="#666666",
        ).pack(anchor="center", pady=(0, 12))

        ttk.Separator(frame, orient="horizontal").pack(
            fill=tk.X, pady=(0, 12))

        # --- Description ---
        ttk.Label(
            frame,
            text=("Keep your game saves safe and organized.\n"
                  "Back up to GitHub and sync between machines."),
            justify=tk.CENTER,
        ).pack(anchor="center", pady=(0, 12))

        # --- Author ---
        author_row = ttk.Frame(frame)
        author_row.pack(anchor="center", pady=2)
        ttk.Label(author_row, text="Made by ").pack(side=tk.LEFT)
        author_link = tk.Label(
            author_row, text=APP_AUTHOR,
            foreground="#0066cc", cursor="hand2",
            font=("Arial", 9, "underline"),
        )
        author_link.pack(side=tk.LEFT)
        author_link.bind(
            "<Button-1>",
            lambda _e: webbrowser.open_new_tab(APP_AUTHOR_URL),
        )

        # --- Repository ---
        repo_row = ttk.Frame(frame)
        repo_row.pack(anchor="center", pady=2)
        ttk.Label(repo_row, text="Repository: ").pack(side=tk.LEFT)
        repo_link = tk.Label(
            repo_row, text=APP_REPO_URL,
            foreground="#0066cc", cursor="hand2",
            font=("Arial", 9, "underline"),
        )
        repo_link.pack(side=tk.LEFT)
        repo_link.bind(
            "<Button-1>",
            lambda _e: webbrowser.open_new_tab(APP_REPO_URL),
        )

        # --- Close ---
        ttk.Button(
            frame, text="Close", width=12, command=dialog.destroy,
        ).pack(anchor="center", pady=(15, 0))

        dialog.bind("<Escape>", lambda _e: dialog.destroy())

        # Center over the main window (same helper used elsewhere)
        from views.utils import center_on_parent
        center_on_parent(dialog, self.root)

    # ------------------------------------------------------------------ #
    # UI — two columns
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        outer.columnconfigure(0, weight=1)   # left list grows
        outer.columnconfigure(1, weight=0)   # right panel fixed
        outer.rowconfigure(0, weight=1)

        # -------- Left: list container --------
        left_container = ttk.LabelFrame(outer, text=" Saved Games ")
        left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_container.rowconfigure(0, weight=1)
        left_container.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(left_container, highlightthickness=0,
                                background="#fbfbfb")
        vscroll = ttk.Scrollbar(left_container, orient="vertical",
                                command=self.canvas.yview)
        self.scroll_frame = ttk.Frame(self.canvas, style="List.TFrame")

        self._scroll_window = self.canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._scroll_window, width=e.width),
        )
        self.canvas.configure(yscrollcommand=vscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all(
            "<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # -------- Right: buttons panel --------
        right = ttk.LabelFrame(outer, text=" Actions ")
        right.grid(row=0, column=1, sticky="ns")

        btn_cfg = {"width": 20}

        ttk.Button(right, text="Import Save",
                   command=self.controller.import_save,
                   **btn_cfg).pack(padx=14, pady=(14, 4))

        ttk.Button(right, text="Refresh",
                   command=self.controller.refresh,
                   **btn_cfg).pack(padx=14, pady=4)

        ttk.Separator(right, orient="horizontal").pack(
            fill=tk.X, padx=14, pady=10)

        ttk.Label(right, text="Selected save:",
                  foreground="#666666").pack(anchor="w", padx=14)
        self.selected_label = ttk.Label(
            right, text="(none)", foreground="#333333",
            wraplength=170, justify=tk.LEFT,
        )
        self.selected_label.pack(anchor="w", padx=14, pady=(0, 10))

        ttk.Button(right, text="Renew",
                   command=self.controller.renew_selected,
                   **btn_cfg).pack(padx=14, pady=4)
        ttk.Button(right, text="Edit",
                   command=self.controller.edit_selected,
                   **btn_cfg).pack(padx=14, pady=4)
        ttk.Button(right, text="Export",
                   command=self.controller.export_selected,
                   **btn_cfg).pack(padx=14, pady=4)
        ttk.Button(right, text="Export Manually",
                   command=self.controller.export_selected_manually,
                   **btn_cfg).pack(padx=14, pady=4)
        ttk.Button(right, text="Sync with Cloud",
                   command=self.controller.sync_with_cloud,
                   **btn_cfg).pack(padx=14, pady=4)
        ttk.Button(right, text="Upload to Cloud",
                   command=self.controller.upload_selected_to_cloud,
                   **btn_cfg).pack(padx=14, pady=4)

        ttk.Separator(right, orient="horizontal").pack(
            fill=tk.X, padx=14, pady=10)

        ttk.Button(right, text="Delete",
                   command=self.controller.delete_selected,
                   **btn_cfg).pack(padx=14, pady=(0, 14))

        ttk.Label(
            right, text=f"v{APP_VERSION}",
            foreground="#999999", font=("Arial", 8),
        ).pack(side=tk.BOTTOM, pady=(10, 4))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #
    def select(self, folder_name):
        if self._selected == folder_name:
            return
        if self._selected and self._selected in self._cards:
            self._cards[self._selected].configure(relief="ridge", borderwidth=1)
        self._selected = folder_name
        if folder_name in self._cards:
            self._cards[folder_name].configure(relief="solid", borderwidth=2)

        save = self._saves_by_folder.get(folder_name)
        if save:
            self.selected_label.configure(text=save.get("title", folder_name))
        else:
            self.selected_label.configure(text="(none)")

        self.controller.on_selection_changed(folder_name)

    def get_selected(self):
        return self._selected

    def get_save(self, folder_name):
        return self._saves_by_folder.get(folder_name)

    # ------------------------------------------------------------------ #
    def refresh(self, saves):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self._thumb_cache.clear()
        self._cards.clear()
        self._saves_by_folder.clear()
        self._selected = None
        self.selected_label.configure(text="(none)")
        self.controller.on_selection_changed(None)

        if not saves:
            ttk.Label(
                self.scroll_frame,
                text="No saves yet.\nUse 'Import Save' on the right to add one.",
                font=("Arial", 11), foreground="#888888",
                justify=tk.CENTER,
            ).pack(pady=40, fill=tk.X)
            return

        for save in saves:
            self._saves_by_folder[save["folder_name"]] = save
            self._create_card(save)

    def _create_card(self, save):
        folder_name = save["folder_name"]

        card = tk.Frame(self.scroll_frame, relief="ridge", borderwidth=1,
                        background="white", cursor="hand2")
        card.pack(fill=tk.X, padx=6, pady=4)
        self._cards[folder_name] = card

        def on_click(_event, fn=folder_name):
            self.select(fn)

        # --- Thumbnail: use a Canvas so we control the pixel size ---
        thumb_canvas = tk.Canvas(card, width=96, height=96,
                                 highlightthickness=0, bd=0,
                                 background="#dddddd")
        thumb_canvas.pack(side=tk.LEFT, padx=8, pady=8)

        thumb_path = save.get("thumbnail")
        loaded = False
        if thumb_path:
            resolved = self.controller.model.resolve_thumbnail(thumb_path)
            if resolved:
                try:
                    img = Image.open(resolved).convert("RGBA").resize(
                        (96, 96), Image.LANCZOS
                    )
                    photo = ImageTk.PhotoImage(img)
                    img.close()
                    self._thumb_cache[folder_name] = photo
                    thumb_canvas.create_image(48, 48, image=photo)
                    loaded = True
                except Exception as e:
                    print("[card] load error for", folder_name, "->", e)
            else:
                print("[card] missing thumbnail:", thumb_path)

        if not loaded:
            thumb_canvas.create_text(48, 48, text="No Image",
                                     fill="#888888", font=("Arial", 9))
            print("[card] showing placeholder for", folder_name)

        info = tk.Frame(card, background="white")
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)

        tk.Label(info, text=save.get("title", "Untitled"),
                 font=("Arial", 13, "bold"),
                 background="white", anchor="w").pack(fill=tk.X, pady=(8, 2))

        description = save.get("description", "")
        if description:
            desc_text = description if len(description) <= 160 else description[:157] + "..."
            tk.Label(info, text=desc_text, wraplength=440, justify=tk.LEFT,
                     foreground="#555555", background="white",
                     anchor="w").pack(fill=tk.X, pady=(0, 4))

        tk.Label(info, text=f"Folder: {folder_name}",
                 foreground="#777777", background="white",
                 anchor="w").pack(fill=tk.X)

        updated = save.get("updated_at")
        if updated:
            display = updated.replace("T", " ").replace("Z", "")[:16]
            tk.Label(info, text=f"Updated: {display}",
                     foreground="#999999", background="white",
                     anchor="w").pack(fill=tk.X)

        # Make everything clickable to select this card.
        def bind_recursive(widget):
            widget.bind("<Button-1>", on_click)
            for child in widget.winfo_children():
                bind_recursive(child)
        bind_recursive(card)