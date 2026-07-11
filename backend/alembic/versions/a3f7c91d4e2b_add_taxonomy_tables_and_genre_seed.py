"""add taxonomy tables and genre seed data

Revision ID: a3f7c91d4e2b
Revises: bb48b53baff5
Create Date: 2026-06-22 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f7c91d4e2b'
down_revision: str | Sequence[str] | None = 'bb48b53baff5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Genre seed data — curated Japanese web novel genres
# ---------------------------------------------------------------------------

_GENRE_SEEDS = [
    # (slug, name_ja, name_en, is_adult, display_order)
    ("isekai-tensei", "異世界転生", "Isekai (Reincarnation)", False, 1),
    ("isekai-tenni", "異世界転移", "Isekai (Transfer)", False, 2),
    ("fantasy", "ファンタジー", "Fantasy", False, 3),
    ("modern-fantasy", "現代ファンタジー", "Modern Fantasy", False, 4),
    ("sf", "SF", "Sci-Fi", False, 5),
    ("romance", "恋愛", "Romance", False, 6),
    ("horror", "ホラー", "Horror", False, 7),
    ("mystery", "ミステリー", "Mystery", False, 8),
    ("action", "アクション", "Action", False, 9),
    ("comedy", "コメディ", "Comedy", False, 10),
    ("drama", "ドラマ", "Drama", False, 11),
    ("slice-of-life", "日常", "Slice of Life", False, 12),
    ("historical", "歴史", "Historical", False, 13),
    ("poetry", "詩", "Poetry", False, 14),
    ("essay", "エッセイ", "Essay", False, 15),
    ("other", "その他", "Other", False, 16),
    ("adult-romance", "大人向け恋愛", "Adult Romance", True, 101),
    ("adult-fantasy", "大人向けファンタジー", "Adult Fantasy", True, 102),
    ("adult-sf", "大人向けSF", "Adult Sci-Fi", True, 103),
    ("adult-other", "大人向けその他", "Adult Other", True, 104),
]


def upgrade() -> None:
    """Create taxonomy tables and seed genre data."""
    # ---- genres ----
    genres_table = op.create_table(
        'genres',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('name_ja', sa.String(length=128), nullable=False),
        sa.Column('name_en', sa.String(length=128), nullable=True),
        sa.Column('is_adult', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_genres')),
    )
    op.create_index(op.f('ix_genres_slug'), 'genres', ['slug'], unique=True)
    op.create_index(op.f('ix_genres_is_active'), 'genres', ['is_active'], unique=False)

    # ---- tags ----
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('name_ja', sa.String(length=255), nullable=True),
        sa.Column('is_adult', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tags')),
    )
    op.create_index(op.f('ix_tags_name'), 'tags', ['name'], unique=True)

    # ---- novel_genres (junction) ----
    op.create_table(
        'novel_genres',
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('genre_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.String(length=32), nullable=False, server_default='system'),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['genre_id'], ['genres.id'], name=op.f('fk_novel_genres_genre_id_genres'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_genres_novel_id_novels'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('novel_id', 'genre_id', name=op.f('pk_novel_genres')),
    )
    op.create_index(op.f('ix_novel_genres_novel_id'), 'novel_genres', ['novel_id'], unique=False)
    op.create_index(op.f('ix_novel_genres_genre_id'), 'novel_genres', ['genre_id'], unique=False)

    # ---- novel_tags (junction) ----
    op.create_table(
        'novel_tags',
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.Column('origin', sa.String(length=32), nullable=False, server_default='unknown'),
        sa.Column('assigned_by', sa.String(length=32), nullable=False, server_default='system'),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], name=op.f('fk_novel_tags_tag_id_tags'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_tags_novel_id_novels'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('novel_id', 'tag_id', name=op.f('pk_novel_tags')),
    )
    op.create_index(op.f('ix_novel_tags_novel_id'), 'novel_tags', ['novel_id'], unique=False)
    op.create_index(op.f('ix_novel_tags_tag_id'), 'novel_tags', ['tag_id'], unique=False)

    # ---- Seed genre data ----
    op.bulk_insert(
        genres_table,
        [
            {
                "slug": slug,
                "name_ja": name_ja,
                "name_en": name_en,
                "is_adult": is_adult,
                "display_order": display_order,
                "is_active": True,
            }
            for slug, name_ja, name_en, is_adult, display_order in _GENRE_SEEDS
        ],
    )


def downgrade() -> None:
    """Drop taxonomy tables."""
    op.drop_index(op.f('ix_novel_tags_tag_id'), table_name='novel_tags')
    op.drop_index(op.f('ix_novel_tags_novel_id'), table_name='novel_tags')
    op.drop_table('novel_tags')
    op.drop_index(op.f('ix_novel_genres_genre_id'), table_name='novel_genres')
    op.drop_index(op.f('ix_novel_genres_novel_id'), table_name='novel_genres')
    op.drop_table('novel_genres')
    op.drop_index(op.f('ix_tags_name'), table_name='tags')
    op.drop_table('tags')
    op.drop_index(op.f('ix_genres_is_active'), table_name='genres')
    op.drop_index(op.f('ix_genres_slug'), table_name='genres')
    op.drop_table('genres')
