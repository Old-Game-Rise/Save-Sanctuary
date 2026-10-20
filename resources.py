# resources.py
import sys
from pathlib import Path


def resource_path(name):
    """
    Return the absolute path to a bundled resource.

    - From source: alongside main.py.
    - PyInstaller (--onefile): inside the temporary _MEIPASS dir.
    - PyInstaller (--onedir): next to the executable.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    return base / name