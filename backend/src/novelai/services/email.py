"""Safe auth email delivery boundary.

The default implementation is intentionally no-op until a real provider is
introduced. It never stores or logs raw tokens or token-bearing URLs.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailDeliveryResult:
    message_type: str
    provider: str
    delivered: bool


@dataclass(frozen=True)
class AuthEmailMessage:
    message_type: str
    recipient: str
    token: str
    url: str


class AuthEmailService(Protocol):
    def send_password_reset_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        """Send or enqueue a password reset email."""

    def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        """Send or enqueue an email verification email."""


def _recipient_fingerprint(email: str) -> str:
    normalized = email.strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:12]


def _safe_path(path: str) -> str:
    if not path.startswith("/") or path.startswith("//"):
        return "/"
    return path


class NoopAuthEmailService:
    """Safe default auth email service.

    It builds the same links a provider would receive, but does not send them
    and does not log the token-bearing URL.
    """

    provider = "noop"

    def __init__(
        self,
        *,
        public_base_url: str,
        password_reset_path: str,
        email_verification_path: str,
    ) -> None:
        self.public_base_url = public_base_url.rstrip("/")
        self.password_reset_path = _safe_path(password_reset_path)
        self.email_verification_path = _safe_path(email_verification_path)

    def send_password_reset_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        self._build_url(path=self.password_reset_path, token=token)
        return self._noop_result(message_type="password_reset", email=email)

    def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        self._build_url(path=self.email_verification_path, token=token)
        return self._noop_result(message_type="email_verification", email=email)

    def _build_url(self, *, path: str, token: str) -> str:
        query = urlencode({"token": token})
        return f"{self.public_base_url}{path}?{query}"

    def _noop_result(self, *, message_type: str, email: str) -> EmailDeliveryResult:
        logger.info(
            "Auth email delivery skipped provider=%s type=%s recipient_hash=%s delivered=false.",
            self.provider,
            message_type,
            _recipient_fingerprint(email),
        )
        return EmailDeliveryResult(message_type=message_type, provider=self.provider, delivered=False)


class InMemoryAuthEmailService(NoopAuthEmailService):
    """Test fake auth email service with an isolated in-memory outbox."""

    provider = "memory"

    def __init__(
        self,
        *,
        public_base_url: str,
        password_reset_path: str,
        email_verification_path: str,
    ) -> None:
        super().__init__(
            public_base_url=public_base_url,
            password_reset_path=password_reset_path,
            email_verification_path=email_verification_path,
        )
        self.outbox: list[AuthEmailMessage] = []

    def send_password_reset_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        self.outbox.append(
            AuthEmailMessage(
                message_type="password_reset",
                recipient=email,
                token=token,
                url=self._build_url(path=self.password_reset_path, token=token),
            )
        )
        return EmailDeliveryResult(message_type="password_reset", provider=self.provider, delivered=True)

    def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        self.outbox.append(
            AuthEmailMessage(
                message_type="email_verification",
                recipient=email,
                token=token,
                url=self._build_url(path=self.email_verification_path, token=token),
            )
        )
        return EmailDeliveryResult(message_type="email_verification", provider=self.provider, delivered=True)
