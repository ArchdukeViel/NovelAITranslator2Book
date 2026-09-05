"""Test application-layer sensitive data encryption utilities.

Reference: REQ-009 / F-9 (postgres-database-hardening-and-security).
Ensures sensitive tokens/credentials are encrypted with authenticated cipher before storage.
"""

from unittest.mock import MagicMock

import pytest

from novelai.config.settings import settings
from novelai.services.provider_credentials import ProviderCredentialService


def test_fernet_credential_encryption_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "PROVIDER_CREDENTIAL_ENCRYPTION_KEY",
        type("Secret", (), {"get_secret_value": lambda self: "test-hardened-key-123456789012345"})(),
    )
    mock_db = MagicMock()
    service = ProviderCredentialService(mock_db)
    secret_token = "sk-ant-api03-very-secret-token-value-12345"

    encrypted = service.encrypt_api_key(secret_token)
    assert encrypted != secret_token
    assert len(encrypted) > len(secret_token)

    # Wrap in mock credential for decryption
    mock_cred = MagicMock()
    mock_cred.encrypted_api_key = encrypted
    decrypted = service.decrypt_api_key(mock_cred)
    assert decrypted == secret_token


def test_decrypt_empty_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "PROVIDER_CREDENTIAL_ENCRYPTION_KEY",
        type("Secret", (), {"get_secret_value": lambda self: "test-hardened-key-123456789012345"})(),
    )
    mock_db = MagicMock()
    service = ProviderCredentialService(mock_db)
    mock_cred = MagicMock()
    mock_cred.encrypted_api_key = None
    with pytest.raises(ValueError, match="no usable encrypted key"):
        service.decrypt_api_key(mock_cred)
