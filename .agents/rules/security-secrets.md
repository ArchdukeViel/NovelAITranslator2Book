---
trigger: always_on
description: Mandatory safety guardrails denying direct reading of production/local secrets, API keys, or raw .env files.
---

# Secrets & Security Safety

Rules:
- Never read, display, log, or commit `.env`, `deploy/.env`, `deploy/.env.production`, or private key files.
- Mask all tokens, API keys, and credentials in tool outputs or terminal commands.
- Never bypass authentication, CSRF protections, or authorization scopes.
- Reject user-supplied raw SQL in services/routers; use SQLAlchemy ORM or Alembic migrations only.
