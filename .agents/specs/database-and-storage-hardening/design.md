# Database and Storage Hardening Design

Spec ID: database-and-storage-hardening
Version: 1.0.0
Status: Active
Updated: 2026-09-05
Requester: Project owner
Owner: Project owner with implementation agent

## Source of Truth Mapping

- Primary architecture: `docs/ARCHITECTURE.md`
- Configuration & secrets: `docs/CONFIGURATION.md`
- Storage invariants: `docs/STORAGE.md`
- Database schema: `backend/alembic/versions/` and `backend/src/novelai/db/models/`
- Active spec: `.agents/specs/database-and-storage-hardening/`

## System Architecture & Component Interaction

```text
+-------------------+        +--------------------+        +-------------------------+
| FastAPI Reader /  | -----> | SQLAlchemy 2.0 ORM | -----> | PostgreSQL 17 (Primary) |
| Admin / Worker    |        | (Session / Engine) |        | [RLS, B-Tree, pg_trgm]  |
+-------------------+        +--------------------+        +-------------------------+
          |                                                             ^
          | HTTP (Cloudflare Access Auth)                               | Metadata Pointers
          v                                                             v
+-------------------+        +--------------------+        +-------------------------+
| R2 Gateway Worker | -----> | Cloudflare R2      | <----> | R2 Incremental Backup   |
| (TypeScript / CF) |        | (dokushodo bucket) |        | (dokushodo-backup)      |
+-------------------+        +--------------------+        +-------------------------+
```

## Data Contracts & Schemas

### 1. Database Connection & Session Scoping Contract

```python
# backend/src/novelai/db/engine.py
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import text
from sqlalchemy.orm import Session

@contextmanager
def session_scope(user_id: str | None = None) -> Generator[Session, None, None]:
    """Execute within a transactional scope with parameterized RLS injection."""
    session = SessionLocal()
    try:
        if user_id:
            session.execute(
                text("SELECT set_config('app.current_user_id', :user_id, true)"),
                {"user_id": str(user_id)},
            )
        yield session
        if session.in_transaction():
            session.commit()
    except Exception:
        if session.in_transaction():
            session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def read_session_scope() -> Generator[Session, None, None]:
    """Read-only transaction scope with tight statement timeout."""
    session = SessionLocal()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        session.execute(text("SET LOCAL statement_timeout = '3000'"))
        yield session
    finally:
        session.close()
```

### 2. Concurrency & Queue Claim Contract

```python
# backend/src/novelai/services/jobs.py
from sqlalchemy import select
from novelai.db.models.chapter import Chapter

def claim_next_pending_chapter(session: Session) -> Chapter | None:
    """Non-blocking, concurrent-safe worker task claim."""
    stmt = (
        select(Chapter)
        .where(Chapter.translation_status == "pending")
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    chapter = session.scalar(stmt)
    if chapter:
        chapter.translation_status = "processing"
        session.commit()
    return chapter
```

### 3. R2 Gateway Cryptographic JWT & Stream Contract

```typescript
// workers/r2-gateway/src/index.ts
import { createRemoteJWKSet, jwtVerify } from "jose";

const JWKS_URL = new URL(
  "https://<team-domain>.cloudflareaccess.com/cdn-cgi/access/certs",
);
const JWKS = createRemoteJWKSet(JWKS_URL);

export async function verifyCloudflareAccessJWT(
  jwt: string,
  expectedAud: string,
): Promise<boolean> {
  try {
    const { payload } = await jwtVerify(jwt, JWKS, {
      audience: expectedAud,
      issuer: "https://<team-domain>.cloudflareaccess.com",
    });
    return typeof payload.common_name === "string";
  } catch {
    return false;
  }
}
```

### 4. Storage Garbage Collection Grace Period & Batching

```python
# backend/src/novelai/storage/r2_cutover.py
from datetime import datetime, timedelta, UTC

GRACE_PERIOD_HOURS = 48

def is_eligible_for_purge(object_metadata: R2ObjectMetadata) -> bool:
    """Never delete objects created within the active grace period."""
    if not object_metadata.last_modified:
        return False
    cutoff = datetime.now(UTC) - timedelta(hours=GRACE_PERIOD_HOURS)
    return object_metadata.last_modified < cutoff
```

## State Machines & Transitions

### Chapter Translation Lifecycle

```text
[pending] --(Worker Claims via SKIP LOCKED)--> [processing]
   |                                                  |
   |                                                  v
   |                                          [QA Evaluation]
   |                                           /           \
   |                              (QA Passed) /             \ (QA Failed)
   |                                         v               v
   +<--(Retry Exhausted: needs_review) [completed]     [needs_retry]
```

### R2 Storage Cutover & GC Lifecycle

```text
[Object Uploaded to R2]
         |
         v
[Unreferenced Scan] --(Age < 48h)--> [Retained in Quarantine]
         | (Age >= 48h and Reference Missing in DB)
         v
[Batch Staged for Deletion]
         | (Operator explicitly invokes with --confirm-delete)
         v
[Purged via Multi-Object Delete API] --> [Audit Record Emitted]
```

## Failure Modes & System Invariants

### Invariants

1. **Connection Budget Rule**: `PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + DB_CONNECTION_RESERVE <= 100`.
2. **Object Immutability Rule**: Byte-immutable chapter bundles under `generations/<id>/` and `novels/<id>/` must never be modified in place.
3. **Fail-Closed Auth Rule**: Unauthenticated requests or invalid JWT signatures must return HTTP 401/403 immediately without hitting downstream storage or database layers.
4. **Zero Unquarantined Storage Loss**: No R2 object younger than 48 hours may be purged by garbage collection routines.
5. **No Blind Overwrites**: All chapter row updates must verify optimistic version tokens (`version_id_col`).

### Failure Modes & Mitigations

- **Database Connection Starvation**: Mitigated by pooling limits, idle timeouts (`pool_recycle=1800`), and statement timeouts (3s reader, 10s migration).
- **Worker Concurrency Collisions**: Mitigated by `FOR UPDATE SKIP LOCKED` and deterministic advisory lock keys using SHA-256.
- **R2 Gateway Transient Spikes**: Mitigated by 3-attempt jittered exponential backoff in client `_request()` loop.
- **Supply-Chain Manifest Tampering**: Mitigated by cryptographic ed25519 signing on backup manifests.
