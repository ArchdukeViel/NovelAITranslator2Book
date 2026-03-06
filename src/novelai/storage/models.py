from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Chapter:
    id: str
    title: str
    text: str


@dataclass
class Novel:
    id: str
    title: str
    author: str | None = None
    chapters: List[Chapter] = field(default_factory=list)
