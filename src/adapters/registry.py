from __future__ import annotations

from dataclasses import dataclass, field

from src.adapters.base import BaseAdapter
from src.adapters.generic import GenericAdapter
from src.adapters.kakuyomu import KakuyomuAdapter
from src.adapters.syosetu import SyosetuAdapter


@dataclass(slots=True)
class AdapterRegistry:
    """Adapter discovery and selection."""

    adapters: list[BaseAdapter] = field(
        default_factory=lambda: [
            SyosetuAdapter(),
            KakuyomuAdapter(),
        ]
    )
    fallback: BaseAdapter = field(default_factory=GenericAdapter)

    def detect(self, url: str, html: str | None = None) -> BaseAdapter:
        for adapter in self.adapters:
            if adapter.can_handle(url, html):
                return adapter
        return self.fallback

    def all(self) -> list[BaseAdapter]:
        return [*self.adapters, self.fallback]

