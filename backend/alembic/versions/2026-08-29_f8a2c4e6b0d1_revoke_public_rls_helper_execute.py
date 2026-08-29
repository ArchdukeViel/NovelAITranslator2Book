"""revoke public execution of the optional Supabase RLS helper

Some Supabase projects create ``public.rls_auto_enable()`` as a
SECURITY DEFINER event-trigger helper.  It is not part of the application
schema, but if present it must not remain callable through the Data API.
Deployments without the optional helper are intentionally a no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f8a2c4e6b0d1"
down_revision: str | Sequence[str] | None = "e7f1a9c3b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regprocedure('public.rls_auto_enable()') IS NOT NULL THEN
                REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM PUBLIC;

                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM anon';
                END IF;

                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM authenticated';
                END IF;
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    # Do not restore broad Data API execution of a SECURITY DEFINER helper.
    pass
