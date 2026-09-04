---
trigger: always_on
description: Alembic database migrations, PostgreSQL schema integrity, connection budgeting, and rollback rules.
---

# Database Migrations & Schema Rules

This rule enforces persistence invariants, schema migration standards, and PostgreSQL connection safety across the Dokushodo backend.

## Migration Generation & File Naming

- **Deterministic Naming**: Every migration file in `backend/alembic/versions/` must use the date-prefixed format:
  ```
  YYYY-MM-DD_<12char_hex_hash>_<short_snake_case_description>.py
  ```
  Example: `2026-09-04_d4e5f6a7b8c9_alter_chapter_title_to_text.py`
- **Immutability of Committed Migrations**:
  - Never edit, rename, or delete past migrations that have been committed or applied to staging/production.
  - If a schema correction is required, create a new forward migration.
- **Reversibility**: Both `upgrade()` and `downgrade()` methods must be fully implemented and reversible.

## Column Types & Model Constraints

- **Text Fields for Content & Titles**: Web novel titles, Japanese episode subtitles, author notes, and chapter HTML bodies must use SQLAlchemy `Text`, never clamped `String(255)` or `String(512)` which trigger PostgreSQL `StringDataRightTruncation` exceptions.
- **Check Constraint Safety**:
  - Do NOT apply ORM-level SQLite table check constraints on `Novel.publication_status` that reject unnormalized legacy strings, because test suites deliberately test reconciliation of unnormalized catalog values (`"strange"` -> `"unknown"`).
  - Use database-level check constraints where appropriate, verified against test suites.

## Connection Pool Budgeting

- The multi-process Compose stack partitions PostgreSQL connections across services (`backend`, `reader`, `worker`):
  $$\text{DB\_POOL\_PROCESS\_COUNT} \times (\text{DB\_POOL\_SIZE} + \text{DB\_MAX\_OVERFLOW}) + \text{DB\_CONNECTION\_RESERVE} \le \text{DB\_CONNECTION\_BUDGET}$$
- For standard `max_connections = 100`:
  - `backend`: pool 5, overflow 5
  - `reader`: pool 5, overflow 5
  - `worker`: pool 5, overflow 5
  - Maintain reserve for migrations and administrative connections.
  - Read configuration values strictly through `novelai.config.settings.settings`.

## Migration Commands

Execute migrations strictly through the project virtualenv:
```powershell
# Check current revision
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current

# Generate new migration file (automatically formats with date-prefix template)
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini revision --autogenerate -m "<short_snake_case_description>"

# Run migrations forward
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head

# Rollback one revision (for local testing)
.venv\Scripts\python.exe -m alembic -c backend/alembic.ini downgrade -1
```
