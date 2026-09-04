"""Export curated data from native PostgreSQL 17 to deploy/postgres/seeds/02-data-seed.sql."""

import json
import os
from datetime import UTC, datetime

import psycopg

TABLES = [
    "users",
    "genres",
    "tags",
    "novels",
    "chapters",
    "email_verification_tokens",
    "provider_credentials",
    "novel_glossary_entries",
    "novel_glossary_decision_events",
    "contributor_usage_ledger",
    "activity_records",
    "analytics_events",
    "notifications",
    "notification_deliveries",
]

SEQUENCES = [
    ("users_id_seq", "SELECT COALESCE(MAX(id), 1) FROM users"),
    ("genres_id_seq", "SELECT COALESCE(MAX(id), 1) FROM genres"),
    ("tags_id_seq", "SELECT COALESCE(MAX(id), 1) FROM tags"),
    ("novels_id_seq", "SELECT COALESCE(MAX(id), 1) FROM novels"),
    ("chapters_id_seq", "SELECT COALESCE(MAX(id), 1) FROM chapters"),
    ("provider_credentials_id_seq", "SELECT COALESCE(MAX(id), 1) FROM provider_credentials"),
    ("novel_glossary_entries_id_seq", "SELECT COALESCE(MAX(id), 1) FROM novel_glossary_entries"),
    ("novel_glossary_decision_events_id_seq", "SELECT COALESCE(MAX(id), 1) FROM novel_glossary_decision_events"),
    ("contributor_usage_ledger_id_seq", "SELECT COALESCE(MAX(id), 1) FROM contributor_usage_ledger"),
    ("notifications_id_seq", "SELECT COALESCE(MAX(id), 1) FROM notifications"),
    ("notification_deliveries_id_seq", "SELECT COALESCE(MAX(id), 1) FROM notification_deliveries"),
]


def format_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, datetime):
        return "'" + v.isoformat() + "'"
    if isinstance(v, (dict, list)):
        escaped = json.dumps(v, ensure_ascii=False).replace("'", "''")
        return "'" + escaped + "'"
    if isinstance(v, str):
        lines = [line.rstrip() for line in v.splitlines()]
        escaped = "\n".join(lines).replace("'", "''")
        return "'" + escaped + "'"
    escaped = str(v).replace("'", "''")
    return "'" + escaped + "'"


def main():
    lines = [
        "-- Dokushodo Curated Relational Data Seed",
        "-- Exported for native PostgreSQL 17",
        f"-- Timestamp: {datetime.now(UTC).isoformat()}",
        "",
        "BEGIN;",
        "",
        "-- Disable triggers and foreign key checks during seed load",
        "SET session_replication_role = 'replica';",
        "",
    ]

    conn_str = os.environ.get("DATABASE_URL")
    if not conn_str:
        raise RuntimeError("DATABASE_URL must be set in the environment to run export_seed.py")
    if conn_str.startswith("postgresql+psycopg://"):
        conn_str = conn_str.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(conn_str) as conn, conn.cursor() as cur:
        for tbl in TABLES:
            cur.execute(f'SELECT * FROM "{tbl}"')
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            lines.append(f"-- Table: {tbl} ({len(rows)} rows)")
            for row in rows:
                col_names = ", ".join(f'"{c}"' for c in cols)
                val_strs = ", ".join(format_val(v) for v in row)
                lines.append(f'INSERT INTO "{tbl}" ({col_names}) VALUES ({val_strs}) ON CONFLICT DO NOTHING;')
            lines.append("")

        lines.append("-- Restore triggers and foreign key checks")
        lines.append("SET session_replication_role = 'origin';")
        lines.append("")
        lines.append("-- Synchronize primary key sequences")
        for seq, q in SEQUENCES:
            cur.execute(q)
            max_val = cur.fetchone()[0]
            lines.append(f"SELECT setval('{seq}', {max_val}, true);")

        lines.append("")
        lines.append("COMMIT;")

    with open("deploy/postgres/seeds/02-data-seed.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Successfully exported curated seed to deploy/postgres/seeds/02-data-seed.sql")


if __name__ == "__main__":
    main()
