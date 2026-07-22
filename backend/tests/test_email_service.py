from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from novelai.config.settings import AppSettings, settings
from novelai.runtime.container import Container
from novelai.services.email import NoopAuthEmailService, SMTPAuthEmailService


class FakeSMTP:
    instances: list[FakeSMTP] = []

    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.messages = []
        self.closed = False
        FakeSMTP.instances.append(self)

    def starttls(self, *, context) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message) -> None:
        self.messages.append(message)

    def quit(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_smtp():
    FakeSMTP.instances.clear()
    yield
    FakeSMTP.instances.clear()


def _smtp_service() -> SMTPAuthEmailService:
    return SMTPAuthEmailService(
        public_base_url="https://dokushodo.example",
        password_reset_path="/password/reset",
        email_verification_path="/email/verify",
        host="smtp.example",
        port=587,
        username="smtp-user",
        password=SecretStr("smtp-password"),
        from_email="noreply@dokushodo.example",
        from_name="Dokushodo",
        starttls=True,
        use_ssl=False,
        timeout_seconds=7.5,
        smtp_factory=FakeSMTP,
    )


def test_container_default_config_uses_noop_service(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_EMAIL_DELIVERY_MODE", "noop")
    monkeypatch.setattr(settings, "PUBLIC_FRONTEND_URL", "http://127.0.0.1:3000")

    service = Container().auth_email

    assert isinstance(service, NoopAuthEmailService)
    assert service.public_base_url == "http://127.0.0.1:3000"


def test_container_smtp_mode_constructs_smtp_service(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setattr(settings, "PUBLIC_FRONTEND_URL", "http://127.0.0.1:3000")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@dokushodo.example")

    service = Container().auth_email

    assert isinstance(service, SMTPAuthEmailService)


def test_settings_default_public_frontend_url_supports_local_email_links():
    clean_settings = AppSettings(_env_file=None)  # type: ignore[call-arg]

    assert clean_settings.PUBLIC_FRONTEND_URL == "http://127.0.0.1:3000"


def test_container_invalid_email_delivery_mode_fails_clearly(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_EMAIL_DELIVERY_MODE", "bad-mode")

    with pytest.raises(ValueError, match="Unsupported AUTH_EMAIL_DELIVERY_MODE"):
        _ = Container().auth_email


def test_smtp_service_sends_password_reset_email_through_fake_smtp(caplog):
    token = "reset-token-value"
    service = _smtp_service()

    with caplog.at_level(logging.INFO):
        result = service.send_password_reset_email(email="reader@example.com", token=token)

    assert result.delivered is True
    assert result.provider == "smtp"
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example"
    assert smtp.port == 587
    assert smtp.timeout == 7.5
    assert smtp.started_tls is True
    assert smtp.login_args == ("smtp-user", "smtp-password")
    assert smtp.closed is True
    message = smtp.messages[0]
    assert message["To"] == "reader@example.com"
    body = message.get_content()
    assert "https://dokushodo.example/password/reset?token=reset-token-value" in body
    assert token not in caplog.text
    assert "token=" not in caplog.text
    assert "smtp-password" not in caplog.text
    assert "reader@example.com" not in caplog.text


def test_smtp_service_sends_verification_email_through_fake_smtp(caplog):
    token = "verify-token-value"
    service = _smtp_service()

    with caplog.at_level(logging.INFO):
        result = service.send_email_verification_email(email="reader@example.com", token=token)

    assert result.delivered is True
    assert result.message_type == "email_verification"
    message = FakeSMTP.instances[0].messages[0]
    assert message["Subject"] == "Verify your Dokushodo email"
    body = message.get_content()
    assert "https://dokushodo.example/email/verify?token=verify-token-value" in body
    assert token not in caplog.text
    assert "token=" not in caplog.text
    assert "smtp-password" not in caplog.text


def test_smtp_missing_config_returns_safe_delivery_failure(caplog):
    service = SMTPAuthEmailService(
        public_base_url="https://dokushodo.example",
        password_reset_path="/password/reset",
        email_verification_path="/email/verify",
        host=None,
        port=587,
        username=None,
        password=None,
        from_email=None,
        from_name="Dokushodo",
        starttls=True,
        use_ssl=False,
        timeout_seconds=5.0,
        smtp_factory=FakeSMTP,
    )

    with caplog.at_level(logging.WARNING):
        result = service.send_password_reset_email(email="reader@example.com", token="reset-token-value")

    assert result.delivered is False
    assert result.provider == "smtp"
    assert FakeSMTP.instances == []
    assert "reset-token-value" not in caplog.text
    assert "token=" not in caplog.text
    assert "reader@example.com" not in caplog.text


def test_smtp_send_failure_returns_safe_delivery_failure(caplog):
    class FailingSMTP(FakeSMTP):
        def send_message(self, message) -> None:
            raise RuntimeError("send failed")

    service = SMTPAuthEmailService(
        public_base_url="https://dokushodo.example",
        password_reset_path="/password/reset",
        email_verification_path="/email/verify",
        host="smtp.example",
        port=587,
        username=None,
        password=None,
        from_email="noreply@dokushodo.example",
        from_name="Dokushodo",
        starttls=False,
        use_ssl=False,
        timeout_seconds=5.0,
        smtp_factory=FailingSMTP,
    )

    with caplog.at_level(logging.WARNING):
        result = service.send_email_verification_email(email="reader@example.com", token="verify-token-value")

    assert result.delivered is False
    assert result.provider == "smtp"
    assert "verify-token-value" not in caplog.text
    assert "token=" not in caplog.text
    assert "reader@example.com" not in caplog.text
