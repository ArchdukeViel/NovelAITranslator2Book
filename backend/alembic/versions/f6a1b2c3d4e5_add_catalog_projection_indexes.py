"""add catalog projection indexes

Revision ID: f6a1b2c3d4e5
Revises: e4f2d0a9c1b3
Create Date: 2026-06-19 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6a1b2c3d4e5'
down_revision: str | Sequence[str] | None = 'e4f2d0a9c1b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add safe catalog projection indexes for future DB-backed listing."""
    op.create_index(
        'ix_novels_is_published_updated_at',
        'novels',
        ['is_published', 'updated_at'],
        unique=False,
    )
    op.create_index(
        'ix_novels_is_published_publication_status',
        'novels',
        ['is_published', 'publication_status'],
        unique=False,
    )
    op.create_index('ix_novels_language', 'novels', ['language'], unique=False)
    op.create_index('ix_novels_source_site', 'novels', ['source_site'], unique=False)
    op.create_index('ix_novels_source_updated_at', 'novels', ['source_updated_at'], unique=False)
    op.create_index('ix_novels_chapter_count', 'novels', ['chapter_count'], unique=False)
    op.create_index('ix_novels_translated_count', 'novels', ['translated_count'], unique=False)
    op.create_index(
        'ix_novels_latest_chapter_updated_at',
        'novels',
        ['latest_chapter_updated_at'],
        unique=False,
    )
    op.create_index(
        'ix_chapters_novel_id_chapter_number',
        'chapters',
        ['novel_id', 'chapter_number'],
        unique=False,
    )
    op.create_index(
        'ix_chapters_novel_id_translation_status_updated_at',
        'chapters',
        ['novel_id', 'translation_status', 'updated_at'],
        unique=False,
    )


def downgrade() -> None:
    """Remove catalog projection indexes."""
    op.drop_index('ix_chapters_novel_id_translation_status_updated_at', table_name='chapters')
    op.drop_index('ix_chapters_novel_id_chapter_number', table_name='chapters')
    op.drop_index('ix_novels_latest_chapter_updated_at', table_name='novels')
    op.drop_index('ix_novels_translated_count', table_name='novels')
    op.drop_index('ix_novels_chapter_count', table_name='novels')
    op.drop_index('ix_novels_source_updated_at', table_name='novels')
    op.drop_index('ix_novels_source_site', table_name='novels')
    op.drop_index('ix_novels_language', table_name='novels')
    op.drop_index('ix_novels_is_published_publication_status', table_name='novels')
    op.drop_index('ix_novels_is_published_updated_at', table_name='novels')
