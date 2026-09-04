"""Export curated data from native PostgreSQL 17 to deploy/postgres/seeds/02-data-seed.sql."""

import json
import os
from datetime import UTC, datetime

import psycopg
from psycopg import sql

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

SEQUENCES: list[tuple[str, str]] = [
    ("users_id_seq", "users"),
    ("genres_id_seq", "genres"),
    ("tags_id_seq", "tags"),
    ("novels_id_seq", "novels"),
    ("chapters_id_seq", "chapters"),
    ("provider_credentials_id_seq", "provider_credentials"),
    ("novel_glossary_entries_id_seq", "novel_glossary_entries"),
    ("novel_glossary_decision_events_id_seq", "novel_glossary_decision_events"),
    ("contributor_usage_ledger_id_seq", "contributor_usage_ledger"),
    ("notifications_id_seq", "notifications"),
    ("notification_deliveries_id_seq", "notification_deliveries"),
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
            cur.execute(sql.SQL("SELECT * FROM {}").format(sql.Identifier(tbl)))
            if not cur.description:
                continue
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
        for seq, tbl in SEQUENCES:
            cur.execute(sql.SQL("SELECT COALESCE(MAX(id), 1) FROM {}").format(sql.Identifier(tbl)))
            row = cur.fetchone()
            max_val = row[0] if row else 1
            lines.append(f"SELECT setval('{seq}', {max_val}, true);")
        cur.execute(
            """
            SELECT s.relname AS seq_name, t.relname AS tbl_name, a.attname AS col_name
            FROM pg_class s
            JOIN pg_depend d ON d.objid = s.oid
            JOIN pg_class t ON d.refobjid = t.oid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
            WHERE s.relkind = 'S' AND t.relkind = 'r' AND d.deptype = 'a'
            ORDER BY t.relname, s.relname;
            """
        )
        discovered_sequences = cur.fetchall()
        for seq, tbl, col in discovered_sequences:
            if tbl in TABLES:
                cur.execute(
                    sql.SQL("SELECT COALESCE(MAX({}), 1) FROM {}").format(sql.Identifier(col), sql.Identifier(tbl))
                )
                row = cur.fetchone()
                max_val = row[0] if row else 1
                lines.append(f"SELECT setval('{seq}', {max_val}, true);")

        lines.append("")
        lines.append("COMMIT;")

    with open("deploy/postgres/seeds/02-data-seed.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Successfully exported curated seed to deploy/postgres/seeds/02-data-seed.sql")


if __name__ == "__main__":
    main()
