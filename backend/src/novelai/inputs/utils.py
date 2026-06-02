from __future__ import annotations

import mimetypes
from pathlib import Path

from novelai.utils.text_normalization import normalize_text

__all__ = ["guess_content_type", "image_placeholder", "is_image_name", "normalize_text"]


def guess_content_type(name: str) -> str | None:
    content_type, _ = mimetypes.guess_type(name)
    return content_type


def is_image_name(path: str | Path) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def image_placeholder(name: str, index: int) -> str:
    stem = Path(name).stem.replace("_", " ").replace("-", " ").strip() or f"image {index}"
    return f"[Image: {stem}]"
