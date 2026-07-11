"""Safe auth email delivery boundary.

The default implementation is intentionally no-op until a real provider is
introduced. It never stores or logs raw tokens or token-bearing URLs.
"""

from __future__ import annotations

import hashlib
import logging
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol
from urllib.parse import urlencode

from pydantic import SecretStr

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
        ...

    def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        ...


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


class SMTPAuthEmailService(NoopAuthEmailService):
    """SMTP-backed auth email service using only Python stdlib."""

    provider = "smtp"

    def __init__(
        self,
        *,
        public_base_url: str,
        password_reset_path: str,
        email_verification_path: str,
        host: str | None,
        port: int,
        username: str | None,
        password: SecretStr | str | None,
        from_email: str | None,
        from_name: str,
        starttls: bool,
        use_ssl: bool,
        timeout_seconds: float,
        smtp_factory: Callable[..., object] | None = None,
    ) -> None:
        super().__init__(
            public_base_url=public_base_url,
            password_reset_path=password_reset_path,
            email_verification_path=email_verification_path,
        )
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.starttls = starttls
        self.use_ssl = use_ssl
        self.timeout_seconds = timeout_seconds
        self.smtp_factory = smtp_factory

    def send_password_reset_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        if not self._has_required_config():
            return self._missing_config_result(message_type="password_reset", email=email)
        url = self._build_url(path=self.password_reset_path, token=token)
        message = self._build_message(
            recipient=email,
            subject="Reset your Dokushodo password",
            body=(
                "A password reset was requested for your Dokushodo account.\n\n"
                f"Use this link to choose a new password:\n{url}\n\n"
                "This reset link expires soon. If you did not request it, you can ignore this message."
            ),
        )
        return self._send(message, message_type="password_reset", email=email)

    def send_email_verification_email(self, *, email: str, token: str) -> EmailDeliveryResult:
        if not self._has_required_config():
            return self._missing_config_result(message_type="email_verification", email=email)
        url = self._build_url(path=self.email_verification_path, token=token)
        message = self._build_message(
            recipient=email,
            subject="Verify your Dokushodo email",
            body=(
                "Please verify the email address for your Dokushodo account.\n\n"
                f"Use this link to verify your email:\n{url}\n\n"
                "This verification link expires soon. If you did not create this account, you can ignore this message."
            ),
        )
        return self._send(message, message_type="email_verification", email=email)

    def _build_message(self, *, recipient: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((self.from_name, self.from_email or ""))
        message["To"] = recipient
        message.set_content(body)
        return message

    def _send(self, message: EmailMessage, *, message_type: str, email: str) -> EmailDeliveryResult:
        try:
            smtp = self._connect()
            try:
                if self.starttls and not self.use_ssl:
                    smtp.starttls(context=ssl.create_default_context())  # type: ignore[attr-defined]
                password = self._password_value()
                if self.username and password:
                    smtp.login(self.username, password)  # type: ignore[attr-defined]
                smtp.send_message(message)  # type: ignore[attr-defined]
            finally:
                smtp.quit()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "SMTP auth email failed type=%s recipient_hash=%s error=%s.",
                message_type,
                _recipient_fingerprint(email),
                exc.__class__.__name__,
            )
            return EmailDeliveryResult(message_type=message_type, provider=self.provider, delivered=False)

        logger.info(
            "SMTP auth email delivered type=%s recipient_hash=%s.",
            message_type,
            _recipient_fingerprint(email),
        )
        return EmailDeliveryResult(message_type=message_type, provider=self.provider, delivered=True)

    def _has_required_config(self) -> bool:
        return bool(self.host and self.from_email)

    def _missing_config_result(self, *, message_type: str, email: str) -> EmailDeliveryResult:
        logger.warning(
            "SMTP auth email skipped type=%s recipient_hash=%s reason=missing_config.",
            message_type,
            _recipient_fingerprint(email),
        )
        return EmailDeliveryResult(message_type=message_type, provider=self.provider, delivered=False)

    def _connect(self) -> object:
        assert self.host is not None
        factory = self.smtp_factory
        if factory is None:
            factory = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
        return factory(self.host, self.port, timeout=self.timeout_seconds)

    def _password_value(self) -> str | None:
        if isinstance(self.password, SecretStr):
            return self.password.get_secret_value()
        return self.password
