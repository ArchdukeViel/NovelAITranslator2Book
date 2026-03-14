from __future__ import annotations

import mimetypes
import re
from pathlib import Path


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def guess_content_type(name: str) -> str | None:
    content_type, _ = mimetypes.guess_type(name)
    return content_type


def is_image_name(path: str | Path) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def image_placeholder(name: str, index: int) -> str:
    stem = Path(name).stem.replace("_", " ").replace("-", " ").strip() or f"image {index}"
    return f"[Image: {stem}]"
