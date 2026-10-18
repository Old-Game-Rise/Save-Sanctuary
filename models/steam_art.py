import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


STEAM_LIBRARY_URL = (
    "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/library_600x900.jpg"
)
STEAM_HEADER_URL = (
    "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
)


def _top_square_in_place(path):
    """
    Rewrite `path` as a 1:1 image that takes the TOP square of the source.

    - Wide images (w > h): crop horizontally, keep full height.
    - Tall images (h > w): crop vertically, keep the TOP `w` pixels.
    - Already-square images: left untouched.
    """
    p = Path(path)
    with Image.open(p) as src:
        img = src.convert("RGB")

    w, h = img.size
    if w == h:
        img.close()
        return

    if w > h:
        left = (w - h) // 2
        box = (left, 0, left + h, h)
    else:
        box = (0, 0, w, w)

    cropped = img.crop(box)
    img.close()
    cropped.save(p, "JPEG", quality=92)
    cropped.close()


def _download(url, dest_path, timeout):
    """Fetch a URL to disk. Returns True on success, False on any failure."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SaveSanctuary/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            data = resp.read()
        if not data:
            return False
        dest_path.write_bytes(data)
        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def fetch_steam_library_art(appid, timeout=15):
    """
    Download the best available Steam cover art for `appid` into a temp file,
    pre-processed so it's already square (top-anchored for portrait art).

    Tries, in order:
        1. library_600x900.jpg   (600x900 portrait, the "proper" library art)
        2. header.jpg            (460x215 landscape, fallback)

    Returns (path_str, temp_dir_obj) on success, or (None, None) on failure.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="save_sanctuary_"))
    tmp_path = tmp_dir / f"thumb_{appid}.jpg"

    for template in (STEAM_LIBRARY_URL, STEAM_HEADER_URL):
        url = template.format(appid=appid)
        if _download(url, tmp_path, timeout):
            try:
                _top_square_in_place(tmp_path)
            except Exception:
                # Pre-processing failed — keep the raw image; _save_thumbnail
                # will center-crop it downstream.
                pass
            return str(tmp_path), tmp_dir

    # Neither candidate worked.
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
    return None, None


def cleanup_temp(dir_obj):
    """Best-effort recursive cleanup of the temp directory."""
    if not dir_obj:
        return
    try:
        for f in Path(dir_obj).iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        Path(dir_obj).rmdir()
    except OSError:
        pass