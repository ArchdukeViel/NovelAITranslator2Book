"""Test ensuring all foreign key columns across SQLAlchemy models have backing indexes.

Reference: F-5 (postgres-database-hardening-and-security)
Prevents sequential scans and deadlock cascades during child-row deletions.
"""

# Import all model modules to register them on Base.metadata
import novelai.db.models as _models  # pyright: ignore[reportUnusedImport] # noqa: F401
from novelai.db.base import Base


def test_all_foreign_keys_have_backing_indexes() -> None:
    """Every ForeignKey constraint column should have a corresponding index."""
    unindexed_fks: list[str] = []

    for table in Base.metadata.tables.values():
        # Collect all column names that have an index or are part of primary key
        indexed_cols: set[str] = set()
        for pk_col in table.primary_key.columns:
            indexed_cols.add(pk_col.name)
        for idx in table.indexes:
            for col in idx.columns:
                indexed_cols.add(col.name)

        for fk in table.foreign_keys:
            col_name = fk.parent.name
            if col_name not in indexed_cols:
                unindexed_fks.append(f"{table.name}.{col_name} -> {fk.target_fullname}")

    # Known low-churn audit / metadata foreign keys grandfathered or awaiting dedicated migration
    allowed_unindexed_fks: set[str] = {
        "novel_glossary_entries.created_by_user_id -> users.id",
        "novel_glossary_entries.last_seen_chapter_id -> chapters.id",
        "novel_glossary_entries.updated_by_user_id -> users.id",
        "novel_glossary_entries.first_seen_chapter_id -> chapters.id",
        "novel_glossary_decision_events.alias_id -> novel_glossary_aliases.id",
        "novel_glossary_qa_findings.reviewer_user_id -> users.id",
        "users.disabled_by_user_id -> users.id",
        "reading_progress.chapter_id -> chapters.id",
        "reading_history.chapter_id -> chapters.id",
        "novel_requests.novel_id -> novels.id",
        "novel_requests.approved_novel_id -> novels.id",
    }

    violating_fks = [fk for fk in unindexed_fks if fk not in allowed_unindexed_fks]

    assert not violating_fks, f"Found {len(violating_fks)} unexpected unindexed foreign key columns:\n" + "\n".join(
        f"  - {fk}" for fk in violating_fks
    )
