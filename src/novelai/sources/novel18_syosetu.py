from __future__ import annotations

import httpx

from novelai.sources.syosetu_ncode import SyosetuNcodeSource


class Novel18SyosetuSource(SyosetuNcodeSource):
    """Source adapter for Syosetu Novel18 / Nocturne novels."""

    @property
    def key(self) -> str:
        return "novel18_syosetu"

    def matches_url(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            host = httpx.URL(candidate).host or ""
        except Exception:
            return False

        return host.lower() == "novel18.syosetu.com"

    def _normalize_url(self, identifier_or_url: str) -> str:
        novel_id = self.normalize_novel_id(identifier_or_url)
        return f"https://novel18.syosetu.com/{novel_id.strip('/')}/"
