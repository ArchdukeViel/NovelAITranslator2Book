"""remove pg_net and reconcile RLS policies

Revision ID: 3da9f497264c
Revises: 024fcb03c7d0
Create Date: 2026-07-16 16:15:58.470464

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3da9f497264c"
down_revision: str | Sequence[str] | None = "024fcb03c7d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Policy = tuple[str, str, str, str | None, str | None]

OWNER = "(SELECT private.is_owner())"
CURRENT_USER_ID = "(SELECT private.current_user_id())"

ALL_TABLES = (
    "alembic_version",
    "audit_logs",
    "chapters",
    "crawl_jobs",
    "email_verification_tokens",
    "genres",
    "library_items",
    "novel_genres",
    "novel_glossary_aliases",
    "novel_glossary_decision_events",
    "novel_glossary_entries",
    "novel_glossary_qa_findings",
    "novel_glossary_source_provenance",
    "novel_requests",
    "novel_tags",
    "novels",
    "password_reset_tokens",
    "provider_credentials",
    "provider_requests",
    "reading_history",
    "reading_progress",
    "reviews",
    "scheduled_cron_log",
    "scheduler_runtime_states",
    "system_settings",
    "tags",
    "translation_jobs",
    "user_glossary_display_overrides",
    "users",
)

OWNER_ONLY_TABLES = (
    "audit_logs",
    "crawl_jobs",
    "email_verification_tokens",
    "novel_glossary_decision_events",
    "password_reset_tokens",
    "provider_credentials",
    "provider_requests",
    "scheduler_runtime_states",
    "system_settings",
    "translation_jobs",
)

PUBLIC_READ_PREDICATES = {
    "chapters": "EXISTS (SELECT 1 FROM public.novels WHERE novels.id = chapters.novel_id AND novels.is_published = true)",
    "genres": "genres.is_active = true",
    "novel_genres": "EXISTS (SELECT 1 FROM public.novels WHERE novels.id = novel_genres.novel_id AND novels.is_published = true)",
    "novel_glossary_aliases": """EXISTS (
        SELECT 1 FROM public.novel_glossary_entries
        WHERE novel_glossary_entries.id = novel_glossary_aliases.glossary_entry_id
          AND novel_glossary_entries.public_visible = true
          AND novel_glossary_entries.status = 'approved'
          AND EXISTS (
              SELECT 1 FROM public.novels
              WHERE novels.id = novel_glossary_aliases.novel_id
                AND novels.is_published = true
          )
    )""",
    "novel_glossary_entries": """novel_glossary_entries.public_visible = true
        AND novel_glossary_entries.status = 'approved'
        AND EXISTS (
            SELECT 1 FROM public.novels
            WHERE novels.id = novel_glossary_entries.novel_id
              AND novels.is_published = true
        )""",
    "novel_glossary_qa_findings": """novel_glossary_qa_findings.status = 'resolved'
        AND EXISTS (
            SELECT 1 FROM public.novels
            WHERE novels.id = novel_glossary_qa_findings.novel_id
              AND novels.is_published = true
        )""",
    "novel_glossary_source_provenance": """EXISTS (
        SELECT 1 FROM public.novel_glossary_entries
        WHERE novel_glossary_entries.id = novel_glossary_source_provenance.glossary_entry_id
          AND novel_glossary_entries.public_visible = true
          AND novel_glossary_entries.status = 'approved'
          AND EXISTS (
              SELECT 1 FROM public.novels
              WHERE novels.id = novel_glossary_source_provenance.novel_id
                AND novels.is_published = true
          )
    )""",
    "novel_tags": "EXISTS (SELECT 1 FROM public.novels WHERE novels.id = novel_tags.novel_id AND novels.is_published = true)",
    "novels": "novels.is_published = true",
    "tags": "true",
}


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _drop_all_policies(table_name: str) -> None:
    bind = op.get_bind()
    policy_names = bind.execute(
        sa.text(
            """
            SELECT policyname
            FROM pg_policies
            WHERE schemaname = 'public' AND tablename = :table_name
            """
        ),
        {"table_name": table_name},
    ).scalars()
    for policy_name in policy_names:
        op.execute(
            f"DROP POLICY {_quote_identifier(str(policy_name))} "
            f"ON public.{_quote_identifier(table_name)}"
        )


def _existing_roles(role_names: str) -> str | None:
    requested_roles = [role_name.strip() for role_name in role_names.split(",")]
    existing_roles = set(
        op.get_bind()
        .execute(
            sa.text("SELECT rolname FROM pg_roles WHERE rolname = ANY(:role_names)"),
            {"role_names": requested_roles},
        )
        .scalars()
    )
    available_roles = [role_name for role_name in requested_roles if role_name in existing_roles]
    return ", ".join(available_roles) or None


def _create_policy(table_name: str, policy: Policy) -> None:
    policy_name, command, roles, using_expression, check_expression = policy
    available_roles = _existing_roles(roles)
    if available_roles is None:
        return
    statement = (
        f"CREATE POLICY {_quote_identifier(policy_name)} "
        f"ON public.{_quote_identifier(table_name)} "
        f"AS PERMISSIVE FOR {command} TO {available_roles}"
    )
    if using_expression is not None:
        statement += f" USING ({using_expression})"
    if check_expression is not None:
        statement += f" WITH CHECK ({check_expression})"
    op.execute(statement)


def _owner_write_policies(table_name: str) -> list[Policy]:
    return [
        (f"Owner can insert {table_name}", "INSERT", "authenticated", None, OWNER),
        (f"Owner can update {table_name}", "UPDATE", "authenticated", OWNER, OWNER),
        (f"Owner can delete {table_name}", "DELETE", "authenticated", OWNER, None),
    ]


def _policies() -> dict[str, list[Policy]]:
    policies: dict[str, list[Policy]] = {
        table_name: [
            (f"Owner has full access to {table_name}", "ALL", "authenticated", OWNER, OWNER)
        ]
        for table_name in OWNER_ONLY_TABLES
    }
    policies["alembic_version"] = [
        ("Owner can read alembic_version", "SELECT", "authenticated", OWNER, None)
    ]

    for table_name, public_predicate in PUBLIC_READ_PREDICATES.items():
        policies[table_name] = [
            (
                f"Owner or public-read for {table_name}",
                "SELECT",
                "anon, authenticated",
                f"{OWNER} OR ({public_predicate})",
                None,
            ),
            *_owner_write_policies(table_name),
        ]

    policies["users"] = [
        ("Owner or self-read for users", "SELECT", "authenticated", f"{OWNER} OR users.id = {CURRENT_USER_ID}", None),
        ("Owner or self-update for users", "UPDATE", "authenticated", f"{OWNER} OR users.id = {CURRENT_USER_ID}", f"{OWNER} OR users.id = {CURRENT_USER_ID}"),
        ("Owner can insert users", "INSERT", "authenticated", None, OWNER),
        ("Owner can delete users", "DELETE", "authenticated", OWNER, None),
    ]
    policies["library_items"] = [
        ("Owner or user-read for library_items", "SELECT", "authenticated", f"{OWNER} OR library_items.user_id = {CURRENT_USER_ID}", None),
        ("Owner or user-insert for library_items", "INSERT", "authenticated", None, f"{OWNER} OR library_items.user_id = {CURRENT_USER_ID}"),
        ("Owner or user-delete for library_items", "DELETE", "authenticated", f"{OWNER} OR library_items.user_id = {CURRENT_USER_ID}", None),
    ]
    policies["novel_requests"] = [
        ("Owner or user-read for novel_requests", "SELECT", "authenticated", f"{OWNER} OR novel_requests.user_id = {CURRENT_USER_ID}", None),
        ("Owner or user-insert for novel_requests", "INSERT", "authenticated", None, f"{OWNER} OR novel_requests.user_id = {CURRENT_USER_ID}"),
    ]
    policies["reading_history"] = [
        ("Owner or user-read for reading_history", "SELECT", "authenticated", f"{OWNER} OR reading_history.user_id = {CURRENT_USER_ID}", None),
        ("Owner or user-insert for reading_history", "INSERT", "authenticated", None, f"{OWNER} OR reading_history.user_id = {CURRENT_USER_ID}"),
    ]
    policies["reading_progress"] = [
        ("Owner or user-read for reading_progress", "SELECT", "authenticated", f"{OWNER} OR reading_progress.user_id = {CURRENT_USER_ID}", None),
        ("Owner or user-insert for reading_progress", "INSERT", "authenticated", None, f"{OWNER} OR reading_progress.user_id = {CURRENT_USER_ID}"),
        ("Owner or user-update for reading_progress", "UPDATE", "authenticated", f"{OWNER} OR reading_progress.user_id = {CURRENT_USER_ID}", f"{OWNER} OR reading_progress.user_id = {CURRENT_USER_ID}"),
    ]
    policies["reviews"] = [
        ("Owner or public-read for reviews", "SELECT", "anon, authenticated", f"{OWNER} OR EXISTS (SELECT 1 FROM public.novels WHERE novels.id = reviews.novel_id AND novels.is_published = true)", None),
        ("Owner or user-insert for reviews", "INSERT", "authenticated", None, f"{OWNER} OR reviews.user_id = {CURRENT_USER_ID}"),
        ("Owner or user-update for reviews", "UPDATE", "authenticated", f"{OWNER} OR reviews.user_id = {CURRENT_USER_ID}", f"{OWNER} OR reviews.user_id = {CURRENT_USER_ID}"),
        ("Owner or user-delete for reviews", "DELETE", "authenticated", f"{OWNER} OR reviews.user_id = {CURRENT_USER_ID}", None),
    ]
    policies["user_glossary_display_overrides"] = [
        ("Owner or user-read for user_glossary_display_overrides", "SELECT", "authenticated", f"{OWNER} OR user_glossary_display_overrides.user_id = {CURRENT_USER_ID}", None),
        ("Owner or user-insert for user_glossary_display_overrides", "INSERT", "authenticated", None, f"{OWNER} OR user_glossary_display_overrides.user_id = {CURRENT_USER_ID}"),
        ("Owner or user-update for user_glossary_display_overrides", "UPDATE", "authenticated", f"{OWNER} OR user_glossary_display_overrides.user_id = {CURRENT_USER_ID}", f"{OWNER} OR user_glossary_display_overrides.user_id = {CURRENT_USER_ID}"),
        ("Owner or user-delete for user_glossary_display_overrides", "DELETE", "authenticated", f"{OWNER} OR user_glossary_display_overrides.user_id = {CURRENT_USER_ID}", None),
    ]
    policies["scheduled_cron_log"] = []
    return policies


def upgrade() -> None:
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS private;
        REVOKE ALL ON SCHEMA private FROM PUBLIC;

        CREATE OR REPLACE FUNCTION private.current_user_id()
        RETURNS integer
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
            SELECT id
            FROM public.users
            WHERE auth_provider_subject = (SELECT auth.uid())::text
            LIMIT 1;
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION private.is_owner()
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
            SELECT EXISTS (
                SELECT 1
                FROM public.users
                WHERE auth_provider_subject = (SELECT auth.uid())::text
                  AND role = 'owner'
            );
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION private.cleanup_expired_scheduler_states()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
        DECLARE
            deleted_count INTEGER;
        BEGIN
            DELETE FROM public.scheduler_runtime_states
            WHERE state NOT IN ('running', 'cooldown', 'failed', 'disabled')
              AND updated_at < NOW() - INTERVAL '14 days';
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            INSERT INTO public.scheduled_cron_log (job_name, status, rows_affected)
            VALUES ('cleanup_expired_scheduler_states', 'succeeded', deleted_count);
        EXCEPTION WHEN OTHERS THEN
            INSERT INTO public.scheduled_cron_log (job_name, status, rows_affected, error_message)
            VALUES ('cleanup_expired_scheduler_states', 'failed', 0, SQLERRM);
        END;
        $$;
        """
    )
    for function_name in ("current_user_id", "is_owner", "cleanup_expired_scheduler_states"):
        op.execute(f"REVOKE ALL ON FUNCTION private.{function_name}() FROM PUBLIC")
    policy_roles = _existing_roles("anon, authenticated, service_role")
    if policy_roles is not None:
        op.execute(f"GRANT USAGE ON SCHEMA private TO {policy_roles}")
        for function_name in ("current_user_id", "is_owner"):
            op.execute(f"GRANT EXECUTE ON FUNCTION private.{function_name}() TO {policy_roles}")
    service_role = _existing_roles("service_role")
    if service_role is not None:
        op.execute(f"GRANT EXECUTE ON FUNCTION private.cleanup_expired_scheduler_states() TO {service_role}")

    policies = _policies()
    if set(policies) != set(ALL_TABLES):
        raise RuntimeError("RLS policy inventory does not cover every public application table")
    for table_name in ALL_TABLES:
        op.execute(f"ALTER TABLE public.{_quote_identifier(table_name)} ENABLE ROW LEVEL SECURITY")
        _drop_all_policies(table_name)
        for policy in policies[table_name]:
            _create_policy(table_name, policy)

    data_api_roles = _existing_roles("anon, authenticated")
    if data_api_roles is not None:
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.scheduled_cron_log FROM {data_api_roles}")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
                PERFORM cron.schedule(
                    'cleanup-scheduler-states',
                    '30 3 * * *',
                    'SELECT private.cleanup_expired_scheduler_states();'
                );
            END IF;
        END;
        $$;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.current_user_id()")
    op.execute("DROP FUNCTION IF EXISTS public.is_owner()")
    op.execute("DROP FUNCTION IF EXISTS public.cleanup_expired_scheduler_states()")
    op.execute("DROP EXTENSION IF EXISTS pg_net")


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA public")
    data_api_roles = _existing_roles("anon, authenticated")
    if data_api_roles is not None:
        op.execute(f"GRANT ALL PRIVILEGES ON TABLE public.scheduled_cron_log TO {data_api_roles}")
