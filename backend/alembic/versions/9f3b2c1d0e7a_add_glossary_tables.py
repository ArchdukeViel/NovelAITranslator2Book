"""add glossary tables

Revision ID: 9f3b2c1d0e7a
Revises: c1d2e3f4a5b6
Create Date: 2026-06-30 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9f3b2c1d0e7a'
down_revision: str | Sequence[str] | None = 'c1d2e3f4a5b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create source-agnostic per-novel glossary tables."""
    op.create_table(
        'novel_glossary_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('canonical_term', sa.String(length=255), nullable=False),
        sa.Column('term_type', sa.String(length=64), nullable=False),
        sa.Column('approved_translation', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='candidate'),
        sa.Column('enforcement_level', sa.String(length=32), nullable=False, server_default='none'),
        sa.Column('owner_locked', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('public_visible', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('public_description', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('replacement_policy', sa.String(length=64), nullable=False, server_default='preview_required'),
        sa.Column('matching_policy', sa.String(length=64), nullable=False, server_default='exact_phrase'),
        sa.Column('first_seen_chapter_id', sa.Integer(), nullable=True),
        sa.Column('first_seen_chapter_number', sa.Integer(), nullable=True),
        sa.Column('last_seen_chapter_id', sa.Integer(), nullable=True),
        sa.Column('last_seen_chapter_number', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name=op.f('fk_novel_glossary_entries_created_by_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['first_seen_chapter_id'], ['chapters.id'], name=op.f('fk_novel_glossary_entries_first_seen_chapter_id_chapters'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['last_seen_chapter_id'], ['chapters.id'], name=op.f('fk_novel_glossary_entries_last_seen_chapter_id_chapters'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_glossary_entries_novel_id_novels'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], name=op.f('fk_novel_glossary_entries_updated_by_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_novel_glossary_entries')),
        sa.UniqueConstraint('novel_id', 'canonical_term', name=op.f('uq_novel_glossary_entries_novel_term')),
    )
    op.create_index(op.f('ix_novel_glossary_entries_novel_id'), 'novel_glossary_entries', ['novel_id'], unique=False)
    op.create_index('ix_novel_glossary_entries_novel_id_canonical_term', 'novel_glossary_entries', ['novel_id', 'canonical_term'], unique=False)
    op.create_index('ix_novel_glossary_entries_novel_id_public_visible', 'novel_glossary_entries', ['novel_id', 'public_visible'], unique=False)
    op.create_index('ix_novel_glossary_entries_novel_id_status', 'novel_glossary_entries', ['novel_id', 'status'], unique=False)
    op.create_index('ix_novel_glossary_entries_novel_id_term_type', 'novel_glossary_entries', ['novel_id', 'term_type'], unique=False)

    op.create_table(
        'novel_glossary_aliases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('glossary_entry_id', sa.Integer(), nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('alias_text', sa.String(length=255), nullable=False),
        sa.Column('alias_type', sa.String(length=32), nullable=False, server_default='observed'),
        sa.Column('language', sa.String(length=32), nullable=True),
        sa.Column('text_origin', sa.String(length=64), nullable=True),
        sa.Column('applies_to', sa.String(length=64), nullable=True),
        sa.Column('matching_policy', sa.String(length=64), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['glossary_entry_id'], ['novel_glossary_entries.id'], name=op.f('fk_novel_glossary_aliases_glossary_entry_id_novel_glossary_entries'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_glossary_aliases_novel_id_novels'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_novel_glossary_aliases')),
    )
    op.create_index(op.f('ix_novel_glossary_aliases_glossary_entry_id'), 'novel_glossary_aliases', ['glossary_entry_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_aliases_novel_id'), 'novel_glossary_aliases', ['novel_id'], unique=False)
    op.create_index('ix_novel_glossary_aliases_entry_type', 'novel_glossary_aliases', ['glossary_entry_id', 'alias_type'], unique=False)
    op.create_index('ix_novel_glossary_aliases_novel_alias_type', 'novel_glossary_aliases', ['novel_id', 'alias_text', 'alias_type'], unique=False)

    op.create_table(
        'novel_glossary_source_provenance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('glossary_entry_id', sa.Integer(), nullable=True),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('source_site', sa.String(length=64), nullable=False),
        sa.Column('source_adapter', sa.String(length=64), nullable=False),
        sa.Column('source_novel_id', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('source_chapter_id', sa.String(length=255), nullable=True),
        sa.Column('source_chapter_number', sa.Integer(), nullable=True),
        sa.Column('chapter_id', sa.Integer(), nullable=True),
        sa.Column('raw_source_term', sa.String(length=255), nullable=True),
        sa.Column('observed_translated_term', sa.String(length=255), nullable=True),
        sa.Column('evidence_ref', sa.String(length=512), nullable=True),
        sa.Column('local_reference', sa.String(length=512), nullable=True),
        sa.Column('evidence_quality', sa.String(length=64), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], name=op.f('fk_novel_glossary_source_provenance_chapter_id_chapters'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['glossary_entry_id'], ['novel_glossary_entries.id'], name=op.f('fk_novel_glossary_source_provenance_glossary_entry_id_novel_glossary_entries'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_glossary_source_provenance_novel_id_novels'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_novel_glossary_source_provenance')),
    )
    op.create_index(op.f('ix_novel_glossary_source_provenance_chapter_id'), 'novel_glossary_source_provenance', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_source_provenance_glossary_entry_id'), 'novel_glossary_source_provenance', ['glossary_entry_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_source_provenance_novel_id'), 'novel_glossary_source_provenance', ['novel_id'], unique=False)
    op.create_index('ix_novel_glossary_source_provenance_entry_source', 'novel_glossary_source_provenance', ['glossary_entry_id', 'source_site'], unique=False)
    op.create_index('ix_novel_glossary_source_provenance_novel_source', 'novel_glossary_source_provenance', ['novel_id', 'source_site', 'source_novel_id'], unique=False)

    op.create_table(
        'novel_glossary_decision_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('glossary_entry_id', sa.Integer(), nullable=True),
        sa.Column('alias_id', sa.Integer(), nullable=True),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('old_value_json', sa.Text(), nullable=True),
        sa.Column('new_value_json', sa.Text(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('decision_source', sa.String(length=64), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_novel_glossary_decision_events_actor_user_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['alias_id'], ['novel_glossary_aliases.id'], name=op.f('fk_novel_glossary_decision_events_alias_id_novel_glossary_aliases'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['glossary_entry_id'], ['novel_glossary_entries.id'], name=op.f('fk_novel_glossary_decision_events_glossary_entry_id_novel_glossary_entries'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_glossary_decision_events_novel_id_novels'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_novel_glossary_decision_events')),
    )
    op.create_index(op.f('ix_novel_glossary_decision_events_actor_user_id'), 'novel_glossary_decision_events', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_decision_events_glossary_entry_id'), 'novel_glossary_decision_events', ['glossary_entry_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_decision_events_novel_id'), 'novel_glossary_decision_events', ['novel_id'], unique=False)
    op.create_index('ix_novel_glossary_decision_events_entry_created', 'novel_glossary_decision_events', ['glossary_entry_id', 'created_at'], unique=False)
    op.create_index('ix_novel_glossary_decision_events_novel_created', 'novel_glossary_decision_events', ['novel_id', 'created_at'], unique=False)

    op.create_table(
        'novel_glossary_qa_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=True),
        sa.Column('glossary_entry_id', sa.Integer(), nullable=True),
        sa.Column('finding_type', sa.String(length=64), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='warning'),
        sa.Column('matched_text', sa.String(length=255), nullable=True),
        sa.Column('suggested_text', sa.String(length=255), nullable=True),
        sa.Column('context_ref', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('reviewer_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], name=op.f('fk_novel_glossary_qa_findings_chapter_id_chapters'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['glossary_entry_id'], ['novel_glossary_entries.id'], name=op.f('fk_novel_glossary_qa_findings_glossary_entry_id_novel_glossary_entries'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_novel_glossary_qa_findings_novel_id_novels'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], name=op.f('fk_novel_glossary_qa_findings_reviewer_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_novel_glossary_qa_findings')),
    )
    op.create_index(op.f('ix_novel_glossary_qa_findings_chapter_id'), 'novel_glossary_qa_findings', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_qa_findings_glossary_entry_id'), 'novel_glossary_qa_findings', ['glossary_entry_id'], unique=False)
    op.create_index(op.f('ix_novel_glossary_qa_findings_novel_id'), 'novel_glossary_qa_findings', ['novel_id'], unique=False)
    op.create_index('ix_novel_glossary_qa_findings_chapter_status', 'novel_glossary_qa_findings', ['chapter_id', 'status'], unique=False)
    op.create_index('ix_novel_glossary_qa_findings_entry_status', 'novel_glossary_qa_findings', ['glossary_entry_id', 'status'], unique=False)
    op.create_index('ix_novel_glossary_qa_findings_novel_chapter_status_severity', 'novel_glossary_qa_findings', ['novel_id', 'chapter_id', 'status', 'severity'], unique=False)
    op.create_index('ix_novel_glossary_qa_findings_novel_status_severity', 'novel_glossary_qa_findings', ['novel_id', 'status', 'severity'], unique=False)
    op.create_index('ix_novel_glossary_qa_findings_type_severity', 'novel_glossary_qa_findings', ['finding_type', 'severity'], unique=False)

    op.create_table(
        'user_glossary_display_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('novel_id', sa.Integer(), nullable=False),
        sa.Column('glossary_entry_id', sa.Integer(), nullable=False),
        sa.Column('display_term', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['glossary_entry_id'], ['novel_glossary_entries.id'], name=op.f('fk_user_glossary_display_overrides_glossary_entry_id_novel_glossary_entries'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id'], name=op.f('fk_user_glossary_display_overrides_novel_id_novels'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_glossary_display_overrides_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_glossary_display_overrides')),
        sa.UniqueConstraint('user_id', 'novel_id', 'glossary_entry_id', name=op.f('uq_user_glossary_display_overrides_user_novel_entry')),
    )
    op.create_index(op.f('ix_user_glossary_display_overrides_glossary_entry_id'), 'user_glossary_display_overrides', ['glossary_entry_id'], unique=False)
    op.create_index(op.f('ix_user_glossary_display_overrides_novel_id'), 'user_glossary_display_overrides', ['novel_id'], unique=False)
    op.create_index(op.f('ix_user_glossary_display_overrides_user_id'), 'user_glossary_display_overrides', ['user_id'], unique=False)
    op.create_index('ix_user_glossary_display_overrides_novel_entry', 'user_glossary_display_overrides', ['novel_id', 'glossary_entry_id'], unique=False)


def downgrade() -> None:
    """Drop source-agnostic per-novel glossary tables."""
    op.drop_index('ix_user_glossary_display_overrides_novel_entry', table_name='user_glossary_display_overrides')
    op.drop_index(op.f('ix_user_glossary_display_overrides_user_id'), table_name='user_glossary_display_overrides')
    op.drop_index(op.f('ix_user_glossary_display_overrides_novel_id'), table_name='user_glossary_display_overrides')
    op.drop_index(op.f('ix_user_glossary_display_overrides_glossary_entry_id'), table_name='user_glossary_display_overrides')
    op.drop_table('user_glossary_display_overrides')

    op.drop_index('ix_novel_glossary_qa_findings_type_severity', table_name='novel_glossary_qa_findings')
    op.drop_index('ix_novel_glossary_qa_findings_novel_status_severity', table_name='novel_glossary_qa_findings')
    op.drop_index('ix_novel_glossary_qa_findings_novel_chapter_status_severity', table_name='novel_glossary_qa_findings')
    op.drop_index('ix_novel_glossary_qa_findings_entry_status', table_name='novel_glossary_qa_findings')
    op.drop_index('ix_novel_glossary_qa_findings_chapter_status', table_name='novel_glossary_qa_findings')
    op.drop_index(op.f('ix_novel_glossary_qa_findings_novel_id'), table_name='novel_glossary_qa_findings')
    op.drop_index(op.f('ix_novel_glossary_qa_findings_glossary_entry_id'), table_name='novel_glossary_qa_findings')
    op.drop_index(op.f('ix_novel_glossary_qa_findings_chapter_id'), table_name='novel_glossary_qa_findings')
    op.drop_table('novel_glossary_qa_findings')

    op.drop_index('ix_novel_glossary_decision_events_novel_created', table_name='novel_glossary_decision_events')
    op.drop_index('ix_novel_glossary_decision_events_entry_created', table_name='novel_glossary_decision_events')
    op.drop_index(op.f('ix_novel_glossary_decision_events_novel_id'), table_name='novel_glossary_decision_events')
    op.drop_index(op.f('ix_novel_glossary_decision_events_glossary_entry_id'), table_name='novel_glossary_decision_events')
    op.drop_index(op.f('ix_novel_glossary_decision_events_actor_user_id'), table_name='novel_glossary_decision_events')
    op.drop_table('novel_glossary_decision_events')

    op.drop_index('ix_novel_glossary_source_provenance_novel_source', table_name='novel_glossary_source_provenance')
    op.drop_index('ix_novel_glossary_source_provenance_entry_source', table_name='novel_glossary_source_provenance')
    op.drop_index(op.f('ix_novel_glossary_source_provenance_novel_id'), table_name='novel_glossary_source_provenance')
    op.drop_index(op.f('ix_novel_glossary_source_provenance_glossary_entry_id'), table_name='novel_glossary_source_provenance')
    op.drop_index(op.f('ix_novel_glossary_source_provenance_chapter_id'), table_name='novel_glossary_source_provenance')
    op.drop_table('novel_glossary_source_provenance')

    op.drop_index('ix_novel_glossary_aliases_novel_alias_type', table_name='novel_glossary_aliases')
    op.drop_index('ix_novel_glossary_aliases_entry_type', table_name='novel_glossary_aliases')
    op.drop_index(op.f('ix_novel_glossary_aliases_novel_id'), table_name='novel_glossary_aliases')
    op.drop_index(op.f('ix_novel_glossary_aliases_glossary_entry_id'), table_name='novel_glossary_aliases')
    op.drop_table('novel_glossary_aliases')

    op.drop_index('ix_novel_glossary_entries_novel_id_term_type', table_name='novel_glossary_entries')
    op.drop_index('ix_novel_glossary_entries_novel_id_status', table_name='novel_glossary_entries')
    op.drop_index('ix_novel_glossary_entries_novel_id_public_visible', table_name='novel_glossary_entries')
    op.drop_index('ix_novel_glossary_entries_novel_id_canonical_term', table_name='novel_glossary_entries')
    op.drop_index(op.f('ix_novel_glossary_entries_novel_id'), table_name='novel_glossary_entries')
    op.drop_table('novel_glossary_entries')
