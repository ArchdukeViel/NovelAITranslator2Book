from __future__ import annotations

import httpx

from novelai.core.errors import SourceError
from novelai.infrastructure.http.profiles import PROFILE_NOVEL18_HTML
from novelai.sources.quality import detect_age_gate_page
from novelai.sources.syosetu_ncode import SyosetuNcodeSource
from novelai.sources.taxonomy import NOVEL18_GENRE_MAP


class Novel18SyosetuSource(SyosetuNcodeSource):
    source_key = "novel18_syosetu"
    """Source adapter for Syosetu Novel18 / Nocturne novels."""

    ADULT_SITE_HOSTS = {
        "novel18.syosetu.com",
        "noc.syosetu.com",
        "mnlt.syosetu.com",
        "mid.syosetu.com",
    }
    AGE_GATE_HOST = "nl.syosetu.com"
    AGE_GATE_PATH_PREFIX = "/redirect/ageauth/"
    AGE_CONFIRM_COOKIE_NAME = "over18"
    AGE_CONFIRM_COOKIE_VALUE = "yes"

    @property
    def _request_profile(self) -> str:
        return PROFILE_NOVEL18_HTML

    @property
    def _genre_map(self) -> dict[str, str]:
        """Use the Novel18 genre map which includes adult genre slugs."""
        return NOVEL18_GENRE_MAP

    def can_handle(self, identifier_or_url: str) -> bool:
        candidate = identifier_or_url.strip()
        if not candidate.startswith(("http://", "https://")):
            return False

        try:
            host = httpx.URL(candidate).host or ""
        except Exception:
            return False

        return host.lower() in self.ADULT_SITE_HOSTS

    def _normalize_host(self, identifier_or_url: str) -> str:
        candidate = identifier_or_url.strip()
        if candidate.startswith(("http://", "https://")):
            try:
                host = (httpx.URL(candidate).host or "").lower()
            except Exception:
                host = ""
            if host in self.ADULT_SITE_HOSTS:
                return host
        return "novel18.syosetu.com"

    def _normalize_url(self, identifier_or_url: str) -> str:
        novel_id = self.normalize_novel_id(identifier_or_url)
        return f"https://{self._normalize_host(identifier_or_url)}/{novel_id.strip('/')}/"

    def _build_request_cookies(self) -> httpx.Cookies:
        cookies = httpx.Cookies()
        for domain in {
            ".syosetu.com",
            "syosetu.com",
            ".novel18.syosetu.com",
            "novel18.syosetu.com",
            ".noc.syosetu.com",
            "noc.syosetu.com",
            ".mnlt.syosetu.com",
            "mnlt.syosetu.com",
            ".mid.syosetu.com",
            "mid.syosetu.com",
            ".nl.syosetu.com",
            "nl.syosetu.com",
        }:
            cookies.set(
                self.AGE_CONFIRM_COOKIE_NAME,
                self.AGE_CONFIRM_COOKIE_VALUE,
                domain=domain,
                path="/",
            )
        return cookies

    def _is_age_gate_page(self, final_url: httpx.URL, html: str) -> bool:
        return detect_age_gate_page(html, final_url=str(final_url))

    def _is_allowed_age_gate_target_url(self, requested_url: str, target_url: str) -> bool:
        requested = httpx.URL(requested_url)
        target = httpx.URL(target_url)
        return (
            target.scheme == requested.scheme
            and (target.host or "").lower() in self.ADULT_SITE_HOSTS
            and self.normalize_novel_id(str(target)) == self.normalize_novel_id(requested_url)
        )

    def _validate_fetched_page(self, requested_url: str, final_url: httpx.URL, html: str) -> None:
        if not self._is_age_gate_page(final_url, html):
            return

        raise SourceError(
            "Syosetu Novel18 remained behind the 18+ age verification page after the bounded public "
            "confirmation flow; the chapter content was not stored."
        )
