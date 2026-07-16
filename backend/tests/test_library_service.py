from __future__ import annotations

from unittest.mock import MagicMock

from novelai.services.library_service import LibraryService


def test_list_catalogued_novel_ids_uses_service_database_boundary() -> None:
    storage = MagicMock()
    db_session = MagicMock()
    db_session.execute.return_value.scalars.return_value.all.return_value = ["alpha", "beta"]
    service = LibraryService(storage=storage, db_session=db_session)

    assert service.list_catalogued_novel_ids() == ["alpha", "beta"]
    db_session.execute.assert_called_once()


def test_list_catalogued_novel_ids_without_database_is_empty() -> None:
    service = LibraryService(storage=MagicMock())

    assert service.list_catalogued_novel_ids() == []
