from __future__ import annotations

import httpx

from novelai.core.errors import SourceError
from novelai.sources.syosetu_ncode import SyosetuNcodeSource


class Novel18SyosetuSource(SyosetuNcodeSource):
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
        host = (final_url.host or "").lower()
        if host == self.AGE_GATE_HOST and final_url.path.startswith(self.AGE_GATE_PATH_PREFIX):
            return True

        lowered_html = html.lower()
        return (
            "redirect/ageauth/" in lowered_html
            and ("cookie" in lowered_html or "javascript" in lowered_html)
            and ("18" in lowered_html or "年齢" in html)
        )

    def _validate_fetched_page(self, requested_url: str, final_url: httpx.URL, html: str) -> None:
        if not self._is_age_gate_page(final_url, html):
            return

        raise SourceError(
            "Syosetu Novel18 returned the 18+ age verification page instead of the novel content. "
            "The scraper sent the adult confirmation cookie, but the site still requires browser-side age auth."
        )
