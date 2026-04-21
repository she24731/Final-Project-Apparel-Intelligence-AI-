from __future__ import annotations

from pathlib import Path

# Browsers often send application/octet-stream or omit Content-Type for camera rolls / HEIC.
_IMAGE_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
    ".avif",
}


def looks_like_image_upload(*, filename: str | None, content_type: str | None) -> bool:
    if not filename:
        return False
    suf = Path(filename).suffix.lower()
    if suf in _IMAGE_SUFFIXES:
        return True
    if not content_type:
        return False
    ct = content_type.lower().split(";", 1)[0].strip()
    return ct.startswith("image/")
