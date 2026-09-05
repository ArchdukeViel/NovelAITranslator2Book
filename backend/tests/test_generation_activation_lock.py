"""Test verifying row-level CAS lock in R2GenerationActivationService during activation.

Reference: REQ-013 / F-13 (postgres-database-hardening-and-security).
Ensures novel query uses .with_for_update() to prevent race conditions during generation activation.
"""

from unittest.mock import MagicMock

import pytest

from novelai.services.r2_activation_service import InvalidGenerationManifestError, R2GenerationActivationService


def test_generation_activation_uses_row_level_lock() -> None:
    mock_storage = MagicMock()
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_lock = MagicMock()

    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.with_for_update.return_value = mock_lock
    mock_lock.one_or_none.return_value = None

    service = R2GenerationActivationService(storage=mock_storage, db_session=mock_session)

    with pytest.raises(InvalidGenerationManifestError, match="Novel does not exist"):
        service.activate(
            novel_id="test-novel",
            generation_id="gen-123",
            manifest={"novel_id": "1"},
            expected_generation_id=None,
        )

    # Verify that with_for_update() was called on the query
    mock_filter.with_for_update.assert_called_once()
