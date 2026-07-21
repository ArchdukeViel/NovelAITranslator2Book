from __future__ import annotations

import pytest

from novelai.scripts.migrate_file_to_db import extract_novel_metadata


def test_extract_novel_metadata_emits_canonical_publication_status() -> None:
    result = extract_novel_metadata(
        {
            "novel_id": "n1234ab",
            "title": "Source title",
            "source_key": "syosetu_ncode",
            "publication_status": "Finished",
        }
    )

    assert result["slug"] == "n1234ab"
    assert result["source_site"] == "syosetu_ncode"
    assert result["publication_status"] == "completed"
    assert "status" not in result


def test_extract_novel_metadata_requires_canonical_novel_id() -> None:
    with pytest.raises(KeyError, match="novel_id"):
        extract_novel_metadata({"id": "legacy-id", "title": "Source title"})
