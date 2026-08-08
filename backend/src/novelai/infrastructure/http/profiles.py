"""Request-profile identifiers for the HTTP fetch layer.

A profile separates HTTP clients and cache entries so that identical URLs
fetched with different cookies/headers (e.g. the adult age-confirmation
cookie vs the public site) never share state. One pooled client and one
cache namespace exist per profile.
"""

PROFILE_SYOSETU_API = "syosetu_api"
PROFILE_SYOSETU_HTML = "syosetu_html"
PROFILE_NOVEL18_API = "novel18_api"
PROFILE_NOVEL18_HTML = "novel18_html"
PROFILE_KAKUYOMU_HTML = "kakuyomu_html"
PROFILE_ASSETS = "assets"

ALL_PROFILES = (
    PROFILE_SYOSETU_API,
    PROFILE_SYOSETU_HTML,
    PROFILE_NOVEL18_API,
    PROFILE_NOVEL18_HTML,
    PROFILE_KAKUYOMU_HTML,
    PROFILE_ASSETS,
)
