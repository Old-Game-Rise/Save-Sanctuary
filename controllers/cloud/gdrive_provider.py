import io
import json
import os
import shutil
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from controllers.cloud.base import CloudProvider


# Narrow scope: allows app to only see/manage files it creates/opens.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_FOLDER_NAME = "Save Sanctuary Backups"


class GDriveError(Exception):
    """Raised when a Google Drive operation fails."""


class GDriveProvider(CloudProvider):
    NAME = "Google Drive"

    def __init__(self, app_dir, save_root=None):
        self.app_dir = Path(app_dir).resolve()
        save_root = Path(save_root or self.app_dir).resolve()
        self.user_saves_dir = save_root / "user saves"
        self.local_thumbs_dir = save_root / "thumbnails"
        self.credentials_file = self.app_dir / "credentials.json"
        self.token_file = self.app_dir / "token.json"
        self.service = None
        self._creds = None

    # ------------------------------------------------------------------ #
    # Authentication
    # ------------------------------------------------------------------ #
    def detect(self):
        """Check if credentials exist and try to load them."""
        if not self.credentials_file.exists():
            return {"ready": False, "reason": "credentials.json missing"}

        try:
            self._get_credentials()
            return {"ready": True}
        except Exception as e:
            return {"ready": False, "reason": str(e)}

    def _get_credentials(self):
        """Standard OAuth 2.0 flow for installed apps."""
        if self._creds and self._creds.valid:
            return self._creds

        creds = None
        # Load existing token if available
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(
                    str(self.token_file), SCOPES)
            except Exception:
                creds = None

        # If no valid creds, either refresh or prompt for login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    # Refresh failed (e.g., token revoked), start fresh
                    creds = None

            if not creds:
                if not self.credentials_file.exists():
                    raise GDriveError(
                        f"Missing {self.credentials_file.name}. "
                        "Download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file), SCOPES)
                # run_local_server is blocking; call from a thread in UI.
                creds = flow.run_local_server(port=0)

            # Save the token for next time
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())

        self._creds = creds
        return creds

    def is_ready(self):
        if not self.credentials_file.exists():
            return False
        try:
            self._get_credentials()
            return True
        except Exception:
            return False

    def status_text(self):
        if not self.credentials_file.exists():
            return ("Google Drive credentials not found.\n\n"
                    "Place 'credentials.json' (OAuth 2.0 Desktop app) "
                    "in the app folder.")
        try:
            self._get_credentials()
            return "Ready — signed in to Google Drive."
        except Exception as e:
            return f"Not signed in: {e}"

    # ------------------------------------------------------------------ #
    # Drive Helpers
    # ------------------------------------------------------------------ #
    def _build_service(self):
        if self.service:
            return self.service
        creds = self._get_credentials()
        self.service = build("drive", "v3", credentials=creds)
        return self.service

    def _ensure_folder(self, progress_cb=None):
        """Find or create the backup folder. Returns its ID."""
        report = progress_cb or (lambda _m: None)
        service = self._build_service()

        # Search for existing folder
        query = (
            f"name='{DRIVE_FOLDER_NAME}' and "
            "mimeType='application/vnd.google-apps.folder' and "
            "trashed=false"
        )
        try:
            results = service.files().list(
                q=query, spaces="drive", fields="files(id, name)"
            ).execute()
        except HttpError as e:
            raise GDriveError(f"Failed to search Drive: {e}")

        files = results.get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        report(f"Creating Drive folder '{DRIVE_FOLDER_NAME}'...")
        metadata = {
            "name": DRIVE_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
        }
        try:
            folder = service.files().create(
                body=metadata, fields="id"
            ).execute()
            return folder.get("id")
        except HttpError as e:
            raise GDriveError(f"Failed to create folder: {e}")

    def _upload_file(self, local_path, parent_id, progress_cb=None):
        """Upload a single file to a specific Drive folder."""
        report = progress_cb or (lambda _m: None)
        service = self._build_service()
        local_path = Path(local_path)

        # Check if file with same name exists in the folder
        query = (
            f"name='{local_path.name}' and "
            f"'{parent_id}' in parents and "
            "trashed=false"
        )
        try:
            results = service.files().list(
                q=query, fields="files(id)"
            ).execute()
        except HttpError as e:
            raise GDriveError(f"Failed to check file: {e}")

        existing = results.get("files", [])

        media = MediaFileUpload(str(local_path), resumable=True)
        file_metadata = {"name": local_path.name, "parents": [parent_id]}

        try:
            if existing:
                # Update existing file
                file_id = existing[0]["id"]
                service.files().update(
                    fileId=file_id, media_body=media
                ).execute()
                report(f"Updated: {local_path.name}")
            else:
                # Create new file
                service.files().create(
                    body=file_metadata, media_body=media, fields="id"
                ).execute()
                report(f"Uploaded: {local_path.name}")
        except HttpError as e:
            raise GDriveError(f"Failed to upload {local_path.name}: {e}")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def upload_all(self, progress_cb=None):
        report = progress_cb or (lambda _m: None)

        if not self.is_ready():
            raise GDriveError(self.status_text())

        report("Connecting to Google Drive...")
        folder_id = self._ensure_folder(progress_cb)

        # Upload thumbnails first
        if self.local_thumbs_dir.exists():
            report("Uploading thumbnails...")
            for f in self.local_thumbs_dir.iterdir():
                if f.is_file():
                    self._upload_file(f, folder_id, progress_cb)

        # Upload saves
        if self.user_saves_dir.exists():
            report("Uploading saves...")
            for save_folder in self.user_saves_dir.iterdir():
                if not save_folder.is_dir():
                    continue

                # Create a subfolder in Drive for this save
                save_name = save_folder.name
                query = (
                    f"name='{save_name}' and "
                    f"'{folder_id}' in parents and "
                    "mimeType='application/vnd.google-apps.folder' and "
                    "trashed=false"
                )
                results = self._build_service().files().list(
                    q=query, fields="files(id)"
                ).execute()

                sub_files = results.get("files", [])
                if sub_files:
                    sub_id = sub_files[0]["id"]
                else:
                    report(f"Creating folder for '{save_name}'...")
                    sub_metadata = {
                        "name": save_name,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [folder_id],
                    }
                    sub = self._build_service().files().create(
                        body=sub_metadata, fields="id"
                    ).execute()
                    sub_id = sub.get("id")

                # Upload all files inside the save folder
                for root, _dirs, files in os.walk(save_folder):
                    for fname in files:
                        fpath = Path(root) / fname
                        self._upload_file(fpath, sub_id, progress_cb)

        report("Google Drive backup complete.")
        return f"https://drive.google.com/drive/folders/{folder_id}"

    # Placeholder for download (to be implemented later)
    def pull_all(self, progress_cb=None):
        raise NotImplementedError(
            "Google Drive download is not implemented yet.")

    def compare_with_remote(self, progress_cb=None):
        raise NotImplementedError(
            "Google Drive comparison is not implemented yet.")