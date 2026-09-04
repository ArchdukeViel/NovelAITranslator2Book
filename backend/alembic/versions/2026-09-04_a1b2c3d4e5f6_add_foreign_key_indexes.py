"""add foreign key indexes to optimize cascade updates and joins

Index the 10 unindexed foreign key columns identified in database audit:
- reading_history(chapter_id)
- reading_progress(chapter_id)
- novel_glossary_entries(first_seen_chapter_id)
- novel_glossary_entries(last_seen_chapter_id)
- novel_glossary_entries(created_by_user_id)
- novel_glossary_entries(updated_by_user_id)
- novel_glossary_decision_events(alias_id)
- novel_glossary_qa_findings(reviewer_user_id)
- novel_requests(novel_id)
- novel_requests(approved_novel_id)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f8a2c4e6b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_reading_history_chapter_id", "reading_history", ["chapter_id"], unique=False)
    op.create_index("ix_reading_progress_chapter_id", "reading_progress", ["chapter_id"], unique=False)
    op.create_index(
        "ix_novel_glossary_entries_first_seen_chapter_id",
        "novel_glossary_entries",
        ["first_seen_chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_novel_glossary_entries_last_seen_chapter_id",
        "novel_glossary_entries",
        ["last_seen_chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_novel_glossary_entries_created_by_user_id",
        "novel_glossary_entries",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_novel_glossary_entries_updated_by_user_id",
        "novel_glossary_entries",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_novel_glossary_decision_events_alias_id",
        "novel_glossary_decision_events",
        ["alias_id"],
        unique=False,
    )
    op.create_index(
        "ix_novel_glossary_qa_findings_reviewer_user_id",
        "novel_glossary_qa_findings",
        ["reviewer_user_id"],
        unique=False,
    )
    op.create_index("ix_novel_requests_novel_id", "novel_requests", ["novel_id"], unique=False)
    op.create_index("ix_novel_requests_approved_novel_id", "novel_requests", ["approved_novel_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_novel_requests_approved_novel_id", table_name="novel_requests")
    op.drop_index("ix_novel_requests_novel_id", table_name="novel_requests")
    op.drop_index("ix_novel_glossary_qa_findings_reviewer_user_id", table_name="novel_glossary_qa_findings")
    op.drop_index("ix_novel_glossary_decision_events_alias_id", table_name="novel_glossary_decision_events")
    op.drop_index("ix_novel_glossary_entries_updated_by_user_id", table_name="novel_glossary_entries")
    op.drop_index("ix_novel_glossary_entries_created_by_user_id", table_name="novel_glossary_entries")
    op.drop_index("ix_novel_glossary_entries_last_seen_chapter_id", table_name="novel_glossary_entries")
    op.drop_index("ix_novel_glossary_entries_first_seen_chapter_id", table_name="novel_glossary_entries")
    op.drop_index("ix_reading_progress_chapter_id", table_name="reading_progress")
    op.drop_index("ix_reading_history_chapter_id", table_name="reading_history")
