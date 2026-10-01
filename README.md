# Save Sanctuary

A desktop application for backing up, organizing, and syncing your game save files. Built with Python and Tkinter.

Author: [OldGameRise](https://github.com/Old-Game-Rise)
Repository: [Old-Game-Rise/Save-Sanctuary](https://github.com/Old-Game-Rise/Save-Sanctuary)

---

## Overview

Save Sanctuary keeps your game saves in one place, shows them as visual cards with thumbnails, and lets you back them up to your own private GitHub repository. It works with both single save files and whole save folders, so it handles everything from a lone `.sav` file to a directory full of Cemu or RPCS3 profiles.

Key features:

- Import saves as a single file or an entire folder
- Assign each save a title, description, and thumbnail
- Browse your saves in a scrollable list with visual cards
- Renew a save directly from its original source location without re-importing
- Export saves back to their original location, or anywhere you choose
- Back up and sync to a private GitHub repository using your existing Git credentials
- Compare local and cloud versions before deciding which direction to sync
- Timestamps track when each save was last updated and last uploaded

---

## Requirements

- Windows 10 or later (other platforms should work, but only Windows is officially tested)
- Python 3.10 or later if running from source
- [Pillow](https://python-pillow.org/) for image handling
- [Git](https://git-scm.com/downloads) for cloud features
- Optional: [GitHub CLI](https://cli.github.com/) for a smoother first-time authentication experience

---

## Installation

### Option 1: Windows release

Download the latest release from the [Releases page](https://github.com/Old-Game-Rise/Save-Sanctuary/releases), extract the archive, and run `SaveSanctuary.exe`.

### Option 2: From source

```bash
git clone https://github.com/Old-Game-Rise/Save-Sanctuary.git
cd Save-Sanctuary
pip install pillow
python main.py
```

---

## Usage

### Importing a save

Click **Import Save** and choose whether you want to import a single file or a whole folder. A dialog appears where you can set:

- **Title** - the display name shown on the card
- **Folder name** - the internal name used on disk (kept in sync with the title by default)
- **Description** - optional notes about the save
- **Thumbnail** - an image that gets cropped to a square and resized to 256x256

Once confirmed, the save is copied into the `user saves` folder along with a `config.json` that records its metadata and original location.

### Renewing a save

If you have been playing since your last import and want to refresh the copy inside Save Sanctuary with your latest progress, select the save and click **Renew**. The app copies the current contents of the original save location back into the archive, replacing what was there.

If the original location no longer exists, you are asked whether you want to select a different source. Choosing Yes opens a picker that matches the original import type (file or folder). The recorded original path is not changed by this operation.

### Editing a save

Select a save and click **Edit** to change its title, folder name, description, or thumbnail. Renaming the folder also renames the associated thumbnail.

### Exporting a save

- **Export** writes the save back to the location it was originally imported from.
- **Export Manually** lets you choose any destination, useful for moving saves to another machine or a portable drive.

### Cloud backup and sync

Save Sanctuary uses your local Git installation and its stored credentials to interact with GitHub. It does not store your password or tokens directly.

To use cloud features:

1. Install Git. If you want the smoothest experience, also install and run `gh auth login` once.
2. Make sure you have signed in to GitHub at least once with your Git client (for example, by pushing to any repository), so your credentials are cached by Git Credential Manager.
3. Click **Upload to Cloud** to back up everything to a private repository called `game-save-manager-backups`. The repository is created automatically if it does not exist.

The **Sync with Cloud** button opens a dialog that compares your local saves against the cloud copy and lists any differences. For each save you can see:

- Whether it is in sync, modified, only local, or only in the cloud
- When it was last updated locally
- When it was last updated in the cloud

From there you can choose to upload local changes or download cloud changes in a single action.

### Deleting a save

Select a save and click **Delete**. A confirmation prompt appears before anything is removed. Deleting a save removes its folder and its thumbnail from your local archive but does not touch the cloud backup until the next upload.

---

## Project structure

```
Save-Sanctuary/
├── main.py
├── version.py
├── requirements.txt
├── LICENSE
├── README.md
├── models/
│   └── save_model.py
├── views/
│   ├── main_window.py
│   ├── save_dialog.py
│   ├── confirm_dialog.py
│   ├── cloud_dialog.py
│   ├── sync_dialog.py
│   └── utils.py
└── controllers/
    ├── save_controller.py
    └── cloud/
        ├── base.py
        ├── github_provider.py
        └── manager.py
```

The application follows an MVC structure:

- **models** handle the filesystem, config files, and metadata
- **views** handle all Tkinter widgets and dialogs
- **controllers** wire the two together and own the application logic

---

## Data layout

Inside the application folder, Save Sanctuary creates three directories that are not tracked by Git:

```
user saves/
    <FolderName>/
        config.json
        save/
            ...the actual save files...

thumbnails/
    <FolderName>.png

cloud_backup/
    ...a local Git working copy that mirrors your GitHub repository...
```

The `config.json` for each save contains:

| Field | Description |
| --- | --- |
| title | Display name on the card |
| description | Optional user notes |
| thumbnail | Path to the thumbnail, relative to the app folder |
| original_path | Where the save was imported from |
| original_is_dir | Whether the original was a folder or a single file |
| updated_at | ISO 8601 UTC timestamp of the last local change |
| uploaded_at | ISO 8601 UTC timestamp of the last successful cloud upload |

---

## Building a Windows release

To build your own standalone executable:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name SaveSanctuary main.py
```

The result is placed in `dist/SaveSanctuary/`. Add `--onefile` if you prefer a single executable, though startup will be slightly slower.

---

## Notes on privacy and security

- Save Sanctuary never sends your data anywhere except the GitHub repository you own and control.
- Authentication is delegated entirely to Git and your operating system credential manager. The app does not store or transmit your GitHub password.
- All cloud repositories created by the app are private by default.

---

## Contributing

Issues and pull requests are welcome. If you find a bug, please include:

- Your operating system and Python version
- The steps to reproduce the problem
- Any relevant output from the console or log files

---

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
</｜｜DSML｜｜ parameter>