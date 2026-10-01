import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from models.save_model import SaveModel
from views.main_window import MainWindow
from views.save_dialog import SaveDialog
from views.confirm_dialog import ConfirmDeleteDialog
from views.utils import center_on_parent

from controllers.cloud.manager import CloudManager
from views.cloud_dialog import CloudUploadDialog
from views.sync_dialog import SyncDialog

from views.confirm_dialog import ConfirmDialog


class SaveController:
    """Wires the model and the views together."""

    def __init__(self):
        self.root = tk.Tk()
        self.model = SaveModel()
        self.cloud = CloudManager(self.model.base_dir)
        self.view = MainWindow(self.root, self)
        self._selected_folder = None
        self.refresh()

    def run(self):
        self.root.mainloop()

    # ------------------------------------------------------------------ #
    def refresh(self):
        saves = self.model.list_saves()
        # keep selection if it still exists
        keep = self._selected_folder
        self.view.refresh(saves)
        if keep and any(s["folder_name"] == keep for s in saves):
            self.view.select(keep)

    def on_selection_changed(self, folder_name):
        self._selected_folder = folder_name

    def _get_selected_save(self):
        if not self._selected_folder:
            messagebox.showinfo(
                "No selection",
                "Please select a save first (click on its card).",
                parent=self.root,
            )
            return None
        save = self.view.get_save(self._selected_folder)
        if save is None:
            messagebox.showinfo(
                "No selection",
                "The selected save is no longer available.",
                parent=self.root,
            )
            return None
        return save

    # ------------------------------------------------------------------ #
    # Import
    # ------------------------------------------------------------------ #
    def import_save(self):
        kind = self._ask_import_type()
        if kind is None:
            return

        if kind == "file":
            source = filedialog.askopenfilename(
                title="Select a save file", parent=self.root)
        else:
            source = filedialog.askdirectory(
                title="Select a save folder", parent=self.root)

        if not source:
            return

        dialog = SaveDialog(self.root, title="Import Save")
        self.root.wait_window(dialog)
        if not dialog.result:
            return

        try:
            final_name = self.model.import_save(
                source,
                dialog.result["title"],
                dialog.result["folder_name"],
                dialog.result["thumbnail_path"],
                dialog.result.get("description", ""),
            )
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self.root)
            return

        self.refresh()
        self.view.select(final_name)
        messagebox.showinfo(
            "Import complete",
            f"Save imported as '{final_name}'.",
            parent=self.root,
        )

    # ------------------------------------------------------------------ #
    # Edit
    # ------------------------------------------------------------------ #
    def edit_save(self, save):
        dialog = SaveDialog(self.root, title="Edit Save", save_data=save)
        self.root.wait_window(dialog)
        if not dialog.result:
            return

        try:
            final_name = self.model.update_save(
                save["folder_name"],
                dialog.result["title"],
                dialog.result["folder_name"],
                dialog.result["thumbnail_path"],
                dialog.result["thumbnail_changed"],
                dialog.result.get("description", ""),
            )
        except Exception as exc:
            messagebox.showerror("Edit failed", str(exc), parent=self.root)
            return

        self.refresh()
        self.view.select(final_name)

    def edit_selected(self):
        save = self._get_selected_save()
        if save:
            self.edit_save(save)


    # ------------------------------------------------------------------ #
    # Renew
    # ------------------------------------------------------------------ #
    def renew_save(self, save):
        folder_name = save["folder_name"]
        config = self.model.get_config(folder_name)
        original_path = config.get("original_path", "")
        is_dir = bool(config.get("original_is_dir", True))

        source_override = None
        original_exists = bool(original_path) and Path(original_path).exists()

        if not original_exists:
            display = original_path or "(no path recorded)"
            proceed = self._ask_missing_source(save.get("title", folder_name),
                                               display)
            if not proceed:
                return

            picked = self._pick_renewal_source(is_dir)
            if not picked:
                return
            source_override = picked

        try:
            used = self.model.renew_save(folder_name,
                                         source_override=source_override)
        except Exception as exc:
            messagebox.showerror("Renew failed", str(exc), parent=self.root)
            return

        self.refresh()
        self.view.select(folder_name)
        messagebox.showinfo(
            "Renew complete",
            f"Save refreshed from:\n{used}",
            parent=self.root,
        )

    def renew_selected(self):
        save = self._get_selected_save()
        if save:
            self.renew_save(save)

    def _ask_missing_source(self, title, display_path):
        dialog = ConfirmDialog(
            self.root,
            title="Original save not found",
            message=(
                f"The original save for \"{title}\" could not be found:\n\n"
                f"{display_path}\n\n"
                "Do you want to select a different source?\n\n"
                "Note: the recorded original path will NOT be changed."
            ),
            yes_text="Yes", no_text="No",
        )
        self.root.wait_window(dialog)
        return dialog.result

    def _pick_renewal_source(self, is_dir):
        if is_dir:
            return filedialog.askdirectory(
                title="Select the save folder to renew from",
                parent=self.root,
            )
        return filedialog.askopenfilename(
            title="Select the save file to renew from",
            parent=self.root,
        )

    # ------------------------------------------------------------------ #
    # Delete
    # ------------------------------------------------------------------ #
    def delete_save(self, save):
        confirmed = self._confirm_delete(save.get("title", save["folder_name"]))
        if not confirmed:
            return

        try:
            self.model.delete_save(save["folder_name"])
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc), parent=self.root)
            return

        if self._selected_folder == save["folder_name"]:
            self._selected_folder = None
        self.refresh()

    def delete_selected(self):
        save = self._get_selected_save()
        if save:
            self.delete_save(save)

    def _confirm_delete(self, title):
        dialog = ConfirmDeleteDialog(
            self.root,
            title="Confirm Delete",
            message=(
                f"Are you sure you want to delete the save \"{title}\"?\n\n"
                "This will remove the save from the program and cannot be undone."
            ),
        )
        self.root.wait_window(dialog)
        return dialog.result

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def export_save(self, save):
        try:
            self.model.export_save(save["folder_name"])
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)
            return
        messagebox.showinfo(
            "Export complete",
            f"Exported to:\n{save.get('original_path')}",
            parent=self.root,
        )

    def export_selected(self):
        save = self._get_selected_save()
        if save:
            self.export_save(save)

    def export_manually(self, save):
        config = self.model.get_config(save["folder_name"])
        is_dir = config.get("original_is_dir", True)

        if is_dir:
            target = filedialog.askdirectory(
                title="Select destination folder", parent=self.root)
        else:
            initial = Path(config.get("original_path", "save.dat")).name
            target = filedialog.asksaveasfilename(
                title="Save as", initialfile=initial, parent=self.root)

        if not target:
            return

        try:
            self.model.export_save(save["folder_name"], target)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)
            return

        messagebox.showinfo(
            "Export complete", f"Exported to:\n{target}", parent=self.root)

    def export_selected_manually(self):
        save = self._get_selected_save()
        if save:
            self.export_manually(save)

    # ------------------------------------------------------------------ #
    # Cloud
    # ------------------------------------------------------------------ #
    def upload_to_cloud(self, save=None):
        """Kick off a full backup of every save to the cloud."""
        provider = self.cloud.get_provider()
        provider.detect()

        if not provider.is_ready():
            messagebox.showinfo(
                "Upload to Cloud",
                provider.status_text(),
                parent=self.root,
            )
            return

        saves = self.model.list_saves()
        if not saves:
            messagebox.showinfo(
                "Upload to Cloud",
                "There are no saves to upload yet.",
                parent=self.root,
            )
            return

        dialog = CloudUploadDialog(self.root, self.cloud, len(saves))
        dialog.start()

    def upload_selected_to_cloud(self):
        # The cloud backup mirrors *all* saves, so selection is irrelevant.
        self.upload_to_cloud()

    def sync_with_cloud(self):
        provider = self.cloud.get_provider()
        provider.detect()

        if not provider.is_ready():
            messagebox.showinfo(
                "Sync with Cloud",
                provider.status_text(),
                parent=self.root,
            )
            return

        dialog = SyncDialog(self.root, self.cloud,
                            on_finished=self.refresh)
        self.root.wait_window(dialog)
        
    # ------------------------------------------------------------------ #
    def _ask_import_type(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Import")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        result = {"value": None}

        ttk.Label(dialog, text="What would you like to import?",
                  font=("Arial", 11)).pack(padx=30, pady=(20, 15))

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(padx=20, pady=(0, 20))

        def choose(value):
            result["value"] = value
            dialog.destroy()

        ttk.Button(btn_frame, text="Single File", width=14,
                   command=lambda: choose("file")).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Folder", width=14,
                   command=lambda: choose("folder")).pack(side=tk.LEFT, padx=6)

        dialog.bind("<Escape>", lambda e: dialog.destroy())
        center_on_parent(dialog, self.root)

        self.root.wait_window(dialog)
        return result["value"]