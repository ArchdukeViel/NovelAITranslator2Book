"""Google OAuth client helpers for public user login.

The router depends on this module through ``get_google_oauth_client`` so tests
can replace network behavior without contacting Google.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from novelai.config.settings import settings

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = ("openid", "email", "profile")


@dataclass(frozen=True)
class GoogleOAuthProfile:
    subject: str
    email: str
    email_verified: bool
    display_name: str | None = None


class GoogleOAuthClient:
    """Small Google OAuth client for authorization URL and userinfo exchange."""

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID or "",
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> GoogleOAuthProfile:
        client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": client_secret.get_secret_value() if client_secret else "",
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
            access_token = token_payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("Google token response did not include an access token.")

            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            profile = userinfo_response.json()

        subject = profile.get("sub")
        email = profile.get("email")
        if not isinstance(subject, str) or not subject:
            raise ValueError("Google profile did not include a subject.")
        if not isinstance(email, str) or not email:
            raise ValueError("Google profile did not include an email.")
        email_verified = profile.get("email_verified")
        display_name = profile.get("name")
        return GoogleOAuthProfile(
            subject=subject,
            email=email,
            email_verified=email_verified is True or email_verified == "true",
            display_name=display_name if isinstance(display_name, str) else None,
        )


def get_google_oauth_client() -> GoogleOAuthClient:
    return GoogleOAuthClient()
