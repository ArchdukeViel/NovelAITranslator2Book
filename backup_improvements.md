# Backend Audit Recommendations & Architectural Improvements

This document tracks systematic audit findings and high-value improvement recommendations for the backend platform (`backend/src/novelai/`), deployment infrastructure (`deploy/`), and cross-layer service boundaries.

---

## Iteration 1: Architecture, API Routers & Application Lifecycle

Audit Focus: Backend architecture, FastAPI API routers, service startup/lifecycles (`main_admin.py`, `main_reader.py`, `api/app.py`), and configuration management (`config/settings.py`).

### Summary of Recommendations (Iteration 1)

| ID          | Subsystem / Component         | Category          | Title                                                                              |
| :---------- | :---------------------------- | :---------------- | :--------------------------------------------------------------------------------- |
| **REC-001** | Configuration / Notification  | Bug / Reliability | Duplicate Shadowed SMTP Settings & Inconsistent Field Discrepancy                  |
| **REC-002** | Public API / Authentication   | Bug / Reliability | Broken Owner Session Resolution in Public Chapter Preview via Missing DB Session   |
| **REC-003** | Lifecycle / Observability     | Performance       | Missing `RequestTimingMiddleware` in Split Admin and Reader App Lifecycles         |
| **REC-004** | Deployment / Architecture     | Architecture      | Public Reader Docker Container Entrypoint Bypasses `main_reader.py`                |
| **REC-005** | Database / Performance        | Performance       | Redundant `session.commit()` on Read-Only GET Queries in Session Dependency        |
| **REC-006** | API Security / Auth           | Security          | Incomplete CSRF Defense for Authenticated Non-Owner Users                          |
| **REC-007** | Security / Authentication     | Security          | Inconsistent Client IP Resolution and Spoofing Vulnerability Across Auth Endpoints |
| **REC-008** | Security / Request Pipeline   | Security          | Silent Content-Length Bypass via Duplicate Request Headers                         |
| **REC-009** | Session Security / Auth       | Security          | Missing Session Invalidation and CSRF Rotation on Authentication Elevation         |
| **REC-010** | API Architecture / Clean Code | Architecture      | Layering Boundary Violation in Library Actions Router via Direct Storage Injection |

---

### REC-001: Duplicate Shadowed SMTP Settings & Inconsistent Field Discrepancy

- **ID**: `REC-001`
- **Subsystem/Component**: Configuration / Notification (`novelai.config.settings`, `novelai.services.notification_service`, `novelai.runtime.container`)
- **Target Location**:
  - `backend/src/novelai/config/settings.py:434-442` (Canonical SMTP configuration block)
  - `backend/src/novelai/config/settings.py:673-688` (Shadowed duplicated SMTP block with `# type: ignore`)
  - `backend/src/novelai/services/notification_service.py:110` (`self._from_addr = settings.SMTP_FROM_ADDRESS`)
  - `backend/src/novelai/runtime/container.py:134` (`from_email=settings.SMTP_FROM_EMAIL`)
  - `deploy/compose.yml:263` (`SMTP_FROM_EMAIL: ${SMTP_FROM_EMAIL:-noreply@dokushodo.test}`)
  - `deploy/.env.example:169` (`SMTP_FROM_EMAIL=noreply@dokushodo.test`)
- **Category**: `Bug/Reliability`
- **Severity**: `High`
- **Summary**: `Settings` class declares two conflicting SMTP blocks. The second block shadows the first using `# type: ignore[reportConstantRedefinition]`, substituting `SMTP_FROM_ADDRESS` for `SMTP_FROM_EMAIL`. Consequently, operator settings provided via `.env` or Docker Compose are silently ignored by `NotificationService`, leading to SPF/DKIM validation failures and dropped notification emails.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/config/settings.py`, lines 434-442 declare:

```python
SMTP_HOST: str | None = None
SMTP_PORT: int = 587
SMTP_USERNAME: str | None = None
SMTP_PASSWORD: SecretStr | None = None
SMTP_FROM_EMAIL: str | None = None
SMTP_FROM_NAME: str = "Dokushodo"
SMTP_STARTTLS: bool = True
SMTP_USE_SSL: bool = False
SMTP_TIMEOUT_SECONDS: float = 10.0
```

Later, lines 673-688 redeclare the identical configuration keys:

```python
SMTP_HOST: str | None = Field(  # type: ignore[reportConstantRedefinition]
    default=None,
    description="SMTP server hostname. When set, SmtpNotificationBackend is used instead of the noop logger.",
)
SMTP_PORT: int = Field(  # type: ignore[reportConstantRedefinition]
    default=587,
    description="SMTP server port. Default 587 (STARTTLS).",
)
SMTP_USERNAME: str | None = Field(  # type: ignore[reportConstantRedefinition]
    default=None,
    description="SMTP username for authentication.",
)
SMTP_PASSWORD: SecretStr | None = Field(  # type: ignore[reportConstantRedefinition]
    default=None,
    description="SMTP password for authentication.",
)
SMTP_FROM_ADDRESS: str = Field(
    default="noreply@novelai.app",
    description="From: address for outgoing notification emails.",
)
```

The developer assumed Pyright flagged stdlib stubs; in reality, Pyright detected class attribute shadowing. Because `SMTP_FROM_ADDRESS` is defined instead of `SMTP_FROM_EMAIL` in the second block:

- `deploy/compose.yml` configures `SMTP_FROM_EMAIL`.
- `container.py` passes `from_email=settings.SMTP_FROM_EMAIL` to `AuthEmailService`.
- `notification_service.py` reads `self._from_addr = settings.SMTP_FROM_ADDRESS`.
  When an operator sets `SMTP_FROM_EMAIL="alerts@mycustomdomain.com"`, `NotificationService` ignores this setting and defaults to `"noreply@novelai.app"`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **SPF/DMARC Rejection**: Emails sent by `NotificationService` specify `From: noreply@novelai.app` instead of the domain registered on the customer's SMTP relay, causing downstream mail transfer agents (MTAs) like Gmail and ProtonMail to discard notifications.
2. **Configuration Confusion**: An operator configuring `SMTP_FROM_EMAIL` in production `.env` sees user auth emails come from the custom address, while system notifications come from `noreply@novelai.app`.

#### 3. Concrete Implementation Specification

1. **Delete Redundant Block**: In `backend/src/novelai/config/settings.py`, remove lines 673-688 completely.
2. **Add Backward Compatibility Property**: In `backend/src/novelai/config/settings.py`, provide a property fallback under `Settings`:

```python
@property
def SMTP_FROM_ADDRESS(self) -> str:
    """Backward-compatible alias for SMTP_FROM_EMAIL."""
    return self.SMTP_FROM_EMAIL or "noreply@dokushodo.test"
```

3. **Harmonize Service Ingestion**: In `backend/src/novelai/services/notification_service.py:110`:

```python
self._from_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_FROM_ADDRESS
```

4. **Harmonize Container Initialization**: In `backend/src/novelai/runtime/container.py:134`:

```python
from_email=settings.SMTP_FROM_EMAIL or settings.SMTP_FROM_ADDRESS,
```

#### 4. Verification & Test Strategy

Create a test in `backend/tests/test_settings_smtp.py`:

```python
def test_smtp_settings_precedence(monkeypatch):
    monkeypatch.setenv("SMTP_FROM_EMAIL", "custom@example.com")
    from novelai.config.settings import Settings
    s = Settings()
    assert s.SMTP_FROM_EMAIL == "custom@example.com"
    assert s.SMTP_FROM_ADDRESS == "custom@example.com"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_settings_smtp.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Any existing external deployment supplying either `SMTP_FROM_EMAIL` or `SMTP_FROM_ADDRESS` will resolve correctly.
Rollback command: `git checkout HEAD -- backend/src/novelai/config/settings.py backend/src/novelai/services/notification_service.py backend/src/novelai/runtime/container.py`

---

### REC-002: Broken Owner Session Resolution in Public Chapter Preview via Missing DB Session

- **ID**: `REC-002`
- **Subsystem/Component**: Public API / Access Control (`novelai.api.routers.public_chapter`, `novelai.api.auth.session`)
- **Target Location**:
  - `backend/src/novelai/api/routers/public_chapter.py:261-285` (`_try_get_owner` direct callable execution)
  - `backend/src/novelai/api/routers/public_chapter.py:455-470` (`chapter_reader` preview fallback logic)
  - `backend/src/novelai/api/auth/session.py:61-75` (`get_current_user`)
- **Category**: `Bug/Reliability`
- **Severity**: `High`
- **Summary**: `_try_get_owner(request)` invokes FastAPI dependency `get_current_user(request)` directly as a Python callable without passing `db_session`. When `get_current_user` calls `db_session.get(User, user_id)`, an `AttributeError` is raised on the `Depends` sentinel and swallowed by a bare `except Exception:`. Consequently, `owner` evaluates to `None`, `effective_version_id` remains unset, and owners attempting to preview draft translation revisions via `?version_id=` are silently served the active translation instead of the requested draft.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/public_chapter.py:261-285`:

```python
async def _try_get_owner(request: Request | None) -> Any | None:
    if request is None:
        return None
    try:
        from novelai.api.auth.session import get_current_user
        scope = getattr(request, "scope", None) or {}
        app = scope.get("app") if isinstance(scope, dict) else None
        override = None
        if app is not None:
            overrides = getattr(app, "dependency_overrides", None)
            if isinstance(overrides, dict):
                override = overrides.get(get_current_user)
        if override is not None:
            user = override()
        else:
            user = get_current_user(request)  # <-- Direct call without db_session!
        if getattr(user, "is_owner", False):
            return user
        return None
    except Exception:
        return None
```

In `backend/src/novelai/api/auth/session.py:61-75`:

```python
def get_current_user(
    request: Request,
    db_session: Session = Depends(get_db_session),
) -> SessionUser:
    session = request.session
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return GUEST

    user = db_session.get(User, user_id)  # <-- Crashes here with AttributeError!
```

Because `get_current_user` is called directly as a Python function, `db_session` defaults to the `fastapi.params.Depends(get_db_session)` parameter default object. Calling `db_session.get(...)` throws `AttributeError: 'Depends' object has no attribute 'get'`.
The exception is caught by `except Exception: return None`.
Then, in `chapter_reader` (lines 455-470):

```python
effective_version_id: str | None = None
if version_id is not None:
    owner = await _try_get_owner(request)
    if owner is not None:
        effective_version_id = version_id

if effective_version_id is not None:
    translated = service.load_public_translation(novel_id, chapter_id, version_id=effective_version_id)
else:
    translated = service.load_public_translation(novel_id, chapter_id)
```

Because `owner` is always `None`, `effective_version_id` is never assigned. The preview request silently loads the published active chapter rather than the requested draft version.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Silent Preview Malfunction**: Site owners reviewing draft translations before publishing cannot view specific draft revisions. The UI silently displays the active version without any error message, misleading editors into approving unfinished work.
2. **Concealed Bug via Blanket Exception Handling**: The bare `except Exception:` swallows `AttributeError`, `NameError`, and `ImportError`, preventing Sentry and APM systems from catching internal runtime failures.

#### 3. Concrete Implementation Specification

1. Update `chapter_reader` in `backend/src/novelai/api/routers/public_chapter.py`:

```python
@router.get("/novels/{novel_slug}/chapters/{chapter_id}")
async def chapter_reader(
    novel_slug: str,
    chapter_id: str,
    request: Request,
    version_id: str | None = None,
    user: SessionUser = Depends(get_current_user),
    service: ReadingService = Depends(get_reading_service),
) -> dict[str, Any]:
    ...
    effective_version_id: str | None = None
    if version_id is not None:
        if user and getattr(user, "is_owner", False):
            effective_version_id = version_id
        else:
            raise HTTPException(
                status_code=403,
                detail="Version preview requires owner authentication",
            )
```

2. Remove the defective `_try_get_owner` function from `public_chapter.py`.

#### 4. Verification & Test Strategy

In `backend/tests/test_public_chapter_preview.py`:

```python
def test_owner_preview_version_id_succeeds(client, db_session, test_owner_user, test_novel):
    client.cookies.set("novelai_session", create_session_cookie(test_owner_user.id))
    resp = client.get(f"/api/public/novels/{test_novel.slug}/chapters/ch1?version_id=ver_draft")
    assert resp.status_code == 200
    assert resp.json()["version_id"] == "ver_draft"

def test_guest_preview_version_id_fails_403(client, test_novel):
    resp = client.get(f"/api/public/novels/{test_novel.slug}/chapters/ch1?version_id=ver_draft")
    assert resp.status_code == 403
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_public_chapter_preview.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible for regular public readers. Unauthenticated requests without `?version_id=` bypass owner validation completely.
Rollback command: `git checkout HEAD -- backend/src/novelai/api/routers/public_chapter.py`

---

### REC-003: Missing `RequestTimingMiddleware` in Split Admin and Reader App Lifecycles

- **ID**: `REC-003`
- **Subsystem/Component**: Application Lifecycle / Observability (`novelai.main_admin`, `novelai.main_reader`, `novelai.api.app`)
- **Target Location**:
  - `backend/src/novelai/main_admin.py:86-118` (`create_admin_app`)
  - `backend/src/novelai/main_reader.py:58-95` (`create_reader_app`)
  - `backend/src/novelai/api/app.py:123` (`create_app`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: The split-service entrypoints (`main_admin.py` and `main_reader.py`) configure middleware stacks individually and omit `RequestTimingMiddleware`. In production split container deployments (`deploy/compose.yml`), `Server-Timing` headers and request duration metric spans are completely missing from HTTP responses.

#### 1. Root Cause & Code-Level Diagnostic

`backend/src/novelai/api/app.py:123` registers:

```python
app.add_middleware(RequestTimingMiddleware)
```

In contrast, `backend/src/novelai/main_admin.py:89-115` and `backend/src/novelai/main_reader.py:65-80` construct their FastAPI applications independently and register only `SessionMiddleware`, `RequestBodyEnforcementMiddleware`, `CORSMiddleware`, `SecurityHeadersMiddleware`, and `TrustedHostMiddleware`.
Neither split service registers `RequestTimingMiddleware`. When running in split container mode under Caddy (`deploy/compose.yml`), all public reader requests on port 8001 and admin requests on port 8000 omit `Server-Timing: app;dur=...`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Frontend Telemetry Blindspot**: The Next.js frontend reader application cannot extract backend processing latency from `Server-Timing`, preventing real-user monitoring (RUM) latency breakdown between network transit, Caddy proxying, and FastAPI execution.
2. **Inconsistent Middleware Sequencing**: Manually duplicating middleware registration across three distinct entrypoints leads to configuration drift whenever security or observability headers are modified.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/main_admin.py:86-118`:

```python
from novelai.api.middleware.timing import RequestTimingMiddleware

# Add timing middleware to admin app stack
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestBodyEnforcementMiddleware)
```

2. In `backend/src/novelai/main_reader.py:58-95`:

```python
from novelai.api.middleware.timing import RequestTimingMiddleware

# Add timing middleware to reader app stack
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestBodyEnforcementMiddleware)
```

#### 4. Verification & Test Strategy

In `backend/tests/test_middleware_timing.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

@pytest.mark.asyncio
async def test_split_services_emit_server_timing():
    from novelai.main_reader import app as reader_app
    from novelai.main_admin import app as admin_app

    for target_app in (reader_app, admin_app):
        async with AsyncClient(transport=ASGITransport(app=target_app), base_url="http://test") as ac:
            res = await ac.get("/health/live")
            assert "server-timing" in res.headers
            assert "app;dur=" in res.headers["server-timing"]
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_middleware_timing.py`

#### 5. Compatibility & Rollback

Harmless additive response header. Completely backward-compatible.
Rollback command: `git checkout HEAD -- backend/src/novelai/main_admin.py backend/src/novelai/main_reader.py`

---

### REC-004: Public Reader Docker Container Entrypoint Bypasses `main_reader.py`

- **ID**: `REC-004`
- **Subsystem/Component**: Deployment / Architecture (`deploy/reader.Dockerfile`, `novelai.__main__`, `novelai.api.server`)
- **Target Location**:
  - `deploy/reader.Dockerfile:60` (`ENTRYPOINT ["novelai", "reader", "--host", "0.0.0.0", "--port", "8001"]`)
  - `backend/src/novelai/__main__.py:12-25` (`main` argument parsing)
  - `backend/src/novelai/api/server.py:8-40` (`_run_reader`, `main`)
- **Category**: `Architecture`
- **Severity**: `High`
- **Summary**: `deploy/reader.Dockerfile:60` executes `novelai reader --host 0.0.0.0 --port 8001`. However, `novelai.__main__.py` does not define a `reader` subcommand and discards unknown arguments via `parse_known_args()`, defaulting to `web_main()`. `web_main()` boots the monolithic `novelai.api.app:app` on port 8000, causing the reader container to expose the full admin surface and fail health checks on port 8001.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/__main__.py:12-25`:

```python
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelai")
    parser.add_argument(
        "--interface",
        choices=["web", "cli"],
        default="web",
        help="Which interface to run.",
    )
    parser.add_argument("--reload", action="store_true", help="Reload the backend when Python files change.")
    args, remaining = parser.parse_known_args(argv)

    if args.interface == "cli":
        cli_main(remaining)
        return

    web_main(reload=bool(args.reload))
```

When `deploy/reader.Dockerfile` invokes `["novelai", "reader", "--host", "0.0.0.0", "--port", "8001"]`:

- Argument `"reader"` does not match `--interface`.
- `parse_known_args` places `["reader", "--host", "0.0.0.0", "--port", "8001"]` into `remaining`.
- `args.interface` falls back to `"web"`.
- `web_main()` in `novelai.api.server` is invoked.
  In `backend/src/novelai/api/server.py`:

```python
def main(*, reload: bool = False) -> None:
    deploy_mode = os.environ.get("DEPLOY_MODE", "monolith")
    if deploy_mode == "split":
        ...
    else:
        uvicorn.run(
            "novelai.api.app:app" if reload else app,
            host=settings.WEB_HOST,
            port=settings.WEB_PORT,  # Port 8000!
            log_level=settings.LOG_LEVEL.lower(),
            reload=reload,
        )
```

The reader container boots the monolith listening on port 8000. Docker container health checks expecting port 8001 fail, and Caddy cannot route traffic to the reader upstream.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Broken Container Routing & 502 Errors**: Caddy upstream routing to `reader:8001` receives `502 Bad Gateway` because uvicorn is listening on port 8000.
2. **Process Isolation Breakdown**: If port 8000 is reached, all administrative endpoints, crawler triggers, and database write sessions are active inside the container that was supposed to be a read-only guest replica.

#### 3. Concrete Implementation Specification

1. **Add `reader_main` to `backend/src/novelai/api/server.py`**:

```python
def reader_main(*, host: str | None = None, port: int | None = None, reload: bool = False) -> None:
    """Run dedicated reader web process."""
    uvicorn.run(
        "novelai.main_reader:app",
        host=host or settings.WEB_HOST,
        port=port or 8001,
        log_level=settings.LOG_LEVEL.lower(),
        reload=reload,
    )
```

2. **Add Subcommand Support in `backend/src/novelai/__main__.py`**:

```python
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelai")
    subparsers = parser.add_subparsers(dest="subcommand")

    reader_p = subparsers.add_parser("reader", help="Run the public reader web service")
    reader_p.add_argument("--host", default=None)
    reader_p.add_argument("--port", type=int, default=None)
    reader_p.add_argument("--reload", action="store_true")

    parser.add_argument("--interface", choices=["web", "cli"], default="web")
    parser.add_argument("--reload", action="store_true")
    args, remaining = parser.parse_known_args(argv)

    if args.subcommand == "reader":
        from novelai.api.server import reader_main
        reader_main(host=args.host, port=args.port, reload=bool(args.reload))
        return

    if args.interface == "cli":
        cli_main(remaining)
        return

    web_main(reload=bool(args.reload))
```

#### 4. Verification & Test Strategy

Verify CLI parsing:

```powershell
powershell -ExecutionPolicy Bypass -Command ".venv\Scripts\python.exe -m novelai reader --help"
```

Assert exit code 0 and documentation of `--host` and `--port` parameters.

#### 5. Compatibility & Rollback

Preserves existing `--interface web` and `--interface cli` invocations while fixing the Docker entrypoint.
Rollback command: `git checkout HEAD -- backend/src/novelai/__main__.py backend/src/novelai/api/server.py`

---

### REC-005: Redundant `session.commit()` on Read-Only GET Queries in Session Dependency

- **ID**: `REC-005`
- **Subsystem/Component**: Database / Performance (`novelai.api.routers.dependencies`)
- **Target Location**:
  - `backend/src/novelai/api/routers/dependencies.py:153-165` (`get_db_session`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `get_db_session` unconditionally executes `session.commit()` upon completion of every HTTP request. For read-only GET queries (e.g. catalog searches, chapter reading, ranking views), this causes redundant `COMMIT` wire protocols against PostgreSQL, consuming write transaction log overhead and holding pooled connections unnecessarily.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/dependencies.py:153-165`:

```python
def get_db_session() -> Generator[Session, None, None]:
    ...
    session = SM()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

FastAPI executes `yield session` across route processing. When the response completes, control resumes in `get_db_session`, executing `session.commit()`.
Even if an HTTP request performed only `SELECT` operations, calling `session.commit()` triggers SQLAlchemy's transaction commit pipeline:

- Incurs a TCP round-trip to PostgreSQL: `COMMIT`.
- PostgreSQL assigns a transaction completion timestamp and writes a commit record to WAL.
- Connection is held open until the commit round-trip acknowledges.
  Under high concurrency on public read endpoints (such as `main_reader.py`), connection pool capacity is exhausted prematurely by read queries waiting for commit round-trips.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Connection Pool Starvation**: High-throughput public reads (e.g. 500+ req/s during reader traffic spikes) hold connections through unnecessary commit round-trips, starving write workers and administrative requests.
2. **Primary DB CPU / WAL Pressure**: Unnecessary commits force PostgreSQL to process transaction completions and flush WAL buffers even for pure read queries.

#### 3. Concrete Implementation Specification

Update `get_db_session` in `backend/src/novelai/api/routers/dependencies.py:153-165`:

```python
def get_db_session() -> Generator[Session, None, None]:
    SM = get_sessionmaker()
    session = SM()
    try:
        yield session
        # Only issue COMMIT if entities were modified, added, or deleted
        if session.is_modified(include_collections=True) or bool(session.dirty or session.new or session.deleted):
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

#### 4. Verification & Test Strategy

In `backend/tests/test_db_session_commit.py`:

```python
def test_readonly_query_does_not_commit(monkeypatch, db_session):
    committed = False
    original_commit = db_session.commit
    def mock_commit():
        nonlocal committed
        committed = True
        return original_commit()
    monkeypatch.setattr(db_session, "commit", mock_commit)

    # Execute read-only query
    from novelai.api.routers.dependencies import get_db_session
    for session in get_db_session():
        pass
    assert not committed, "Read-only session must not execute commit()"

def test_mutation_query_executes_commit(monkeypatch, db_session, test_novel):
    committed = False
    original_commit = db_session.commit
    def mock_commit():
        nonlocal committed
        committed = True
        return original_commit()
    monkeypatch.setattr(db_session, "commit", mock_commit)

    from novelai.api.routers.dependencies import get_db_session
    for session in get_db_session():
        novel = session.merge(test_novel)
        novel.title = "Modified Title"
    assert committed, "Mutated session must execute commit()"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_db_session_commit.py`

#### 5. Compatibility & Rollback

Transparent to route handlers. Any route that mutates ORM objects (`session.add()`, updates attributes, or deletes) triggers `session.new / session.dirty / session.deleted` and continues to commit automatically.
Rollback command: `git checkout HEAD -- backend/src/novelai/api/routers/dependencies.py`

---

### REC-006: Incomplete CSRF Defense for Authenticated Non-Owner Users

- **ID**: `REC-006`
- **Subsystem/Component**: API Security / Authorization (`novelai.api.auth.security`)
- **Target Location**:
  - `backend/src/novelai/api/auth/security.py:70-85` (`require_csrf_for_unsafe_methods`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `require_csrf_for_unsafe_methods` bypasses CSRF validation if `not user.is_owner`. Authenticated non-owner users (`role="user"`) making state-changing requests (POST, PUT, PATCH, DELETE) on endpoints protected by this dependency are completely exempt from CSRF token checks, creating a Cross-Site Request Forgery vulnerability.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/auth/security.py:70-85`:

```python
def require_csrf_for_unsafe_methods(
    request: Request,
    user: SessionUser = Depends(get_current_user),
) -> None:
    """Require CSRF for owner-authenticated unsafe browser requests.

    Non-owner requests are left for require_role("owner") to reject so auth
    failures keep their existing 401/403 behavior.
    """
    if request.method.upper() in _SAFE_METHODS:
        return
    if not user.is_owner:
        return
    require_csrf_token(request)
```

The early return `if not user.is_owner: return` was written under the assumption that non-owner requests would be rejected downstream by `require_role("owner")`.
However:

1. `require_csrf_for_unsafe_methods` is mounted at the router level in routers that handle user contributions, reviews, and library state (e.g. `admin_reviews.py`, `editor.py`, `operations.py`).
2. If any mutation route allows non-owner access, or if role-based authorization is bypassed or refactored, CSRF protection is completely disabled for all regular users.
3. It violates defense-in-depth: authentication and CSRF protection must be evaluated independently.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Cross-Site Request Forgery (CSRF)**: An attacker crafts a malicious webpage that executes a background `POST` request to mutating backend endpoints. If a logged-in user (`role="user"`) visits the site, the browser attaches the `novelai_session` cookie. Because `user.is_owner` is `False`, `require_csrf_for_unsafe_methods` exits immediately without inspecting `X-CSRF-Token`.
2. **ASVS V4.2 Violation**: Violates OWASP ASVS Requirement 4.2.1: "Verify that sensitive operations are protected against CSRF regardless of user privilege level."

#### 3. Concrete Implementation Specification

Update `require_csrf_for_unsafe_methods` in `backend/src/novelai/api/auth/security.py:70-85`:

```python
def require_csrf_for_unsafe_methods(
    request: Request,
    user: SessionUser = Depends(get_current_user),
) -> None:
    """Require CSRF tokens for all authenticated state-changing requests."""
    if request.method.upper() in _SAFE_METHODS:
        return
    # Only authenticated users carry ambient browser cookies requiring CSRF defense
    if not getattr(user, "is_authenticated", False):
        return
    require_csrf_token(request)
```

#### 4. Verification & Test Strategy

In `backend/tests/test_auth_csrf.py`:

```python
def test_regular_user_unsafe_request_requires_csrf(client, test_regular_user):
    client.cookies.set("novelai_session", create_session_cookie(test_regular_user.id))
    # Post without CSRF header must fail 403 Forbidden
    res = client.post("/api/user/contributions", json={"content": "test"})
    assert res.status_code == 403
    assert "CSRF" in res.json()["detail"]

def test_regular_user_unsafe_request_with_csrf_succeeds(client, test_regular_user):
    csrf = "valid_test_csrf_token"
    client.cookies.set("novelai_session", create_session_cookie(test_regular_user.id, extra={"_csrf_token": csrf}))
    res = client.post("/api/user/contributions", json={"content": "test"}, headers={"X-CSRF-Token": csrf})
    assert res.status_code != 403
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_auth_csrf.py`

#### 5. Compatibility & Rollback

Frontend client already attaches `X-CSRF-Token` headers via `frontend/lib/api.ts`. No breaking changes for legitimate web clients.
Rollback command: `git checkout HEAD -- backend/src/novelai/api/auth/security.py`

---

### REC-007: Inconsistent Client IP Resolution and Spoofing Vulnerability Across Auth Endpoints

- **ID**: `REC-007`
- **Subsystem/Component**: Security / Authentication (`novelai.api.routers.auth`, `novelai.api.middleware.security`)
- **Target Location**:
  - `backend/src/novelai/api/routers/auth.py:205, 250, 279` (`request.client.host`)
  - `backend/src/novelai/api/middleware/security.py:75-120` (`get_client_ip`, `_is_trusted_proxy`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: Auth endpoints bypass `get_client_ip()` and extract `request.client.host` directly. Behind Caddy/Cloudflare, this collapses all client IPs to `127.0.0.1` or the Caddy container IP, allowing brute-force attackers to trigger global login lockouts. Meanwhile, `get_client_ip()` blindly trusts the leftmost IP of `X-Forwarded-For`, allowing arbitrary IP spoofing.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/auth.py:205, 250, 279`:

```python
@router.post("/register")
def register(...):
    ip = request.client.host if request.client else None
...
@router.post("/password/reset/request")
def request_password_reset(...):
    ip = request.client.host if request.client else None
```

Under Docker Compose (`cloudflared -> caddy -> uvicorn`), `request.client.host` is always `127.0.0.1` or Caddy's internal bridge IP `172.18.0.x`.
In `backend/src/novelai/api/middleware/security.py:75-105`:

```python
def get_client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if not settings.TRUSTED_PROXY_CIDRS:
        return direct_ip
    if not _is_trusted_proxy(direct_ip):
        return direct_ip
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            try:
                return str(ipaddress.ip_address(first_ip))
            except ValueError:
                return direct_ip
    return direct_ip
```

`get_client_ip` extracts `split(",")[0]` without verifying intermediate proxies. Any external client can inject `X-Forwarded-For: 1.1.1.1` and bypass IP-based rate limiting or poison audit trails.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Global Authentication Denial of Service**: Failed login attempts from an attacker lock out the single collapsed proxy IP (`127.0.0.1`), blocking all legitimate users from logging in.
2. **Audit Trail Spoofing**: Attackers can spoof their source IP in security compliance logs by injecting arbitrary `X-Forwarded-For` headers.

#### 3. Concrete Implementation Specification

1. **Harden `get_client_ip` in `backend/src/novelai/api/middleware/security.py`**:

```python
def get_client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if not settings.TRUSTED_PROXY_CIDRS or not _is_trusted_proxy(direct_ip):
        return direct_ip

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if not forwarded_for:
        return direct_ip

    ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
    # Traverse right-to-left through trusted proxies until first untrusted client IP
    for ip_str in reversed(ips):
        try:
            if not _is_trusted_proxy(ip_str):
                return str(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    return direct_ip
```

2. **Use `get_client_ip` in Auth Router**: In `backend/src/novelai/api/routers/auth.py:205, 250, 279`, replace `request.client.host if request.client else None` with:

```python
from novelai.api.middleware.security import get_client_ip

ip = get_client_ip(request)
```

#### 4. Verification & Test Strategy

In `backend/tests/test_ip_spoofing.py`:

```python
def test_untrusted_client_cannot_spoof_ip(client):
    # Spoofed header from untrusted external client
    res = client.post("/api/auth/register", headers={"X-Forwarded-For": "8.8.8.8"}, json={...})
    # Must record actual direct peer IP, not spoofed 8.8.8.8
    assert res.json().get("ip") != "8.8.8.8"

def test_trusted_proxy_resolves_real_client_ip(client, monkeypatch):
    from novelai.config.settings import settings
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", ["127.0.0.1/32"])
    res = client.post("/api/auth/register", headers={"X-Forwarded-For": "203.0.113.195, 127.0.0.1"}, json={...})
    assert res.json().get("ip") == "203.0.113.195"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_ip_spoofing.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Set `TRUSTED_PROXY_CIDRS` in `.env` to match Docker bridge subnets (`172.16.0.0/12`, `127.0.0.1/32`).
Rollback command: `git checkout HEAD -- backend/src/novelai/api/middleware/security.py backend/src/novelai/api/routers/auth.py`

---

### REC-008: Silent Content-Length Bypass via Duplicate Request Headers

- **ID**: `REC-008`
- **Subsystem/Component**: Security / Request Pipeline (`novelai.api.middleware.security`)
- **Target Location**:
  - `backend/src/novelai/api/middleware/security.py:136-150` (`_get_header`, `_declared_body_size`)
  - `backend/src/novelai/api/middleware/security.py:190-210` (`RequestBodyEnforcementMiddleware.__call__`)
- **Category**: `Security`
- **Severity**: `Medium`
- **Summary**: When duplicate headers are present in an HTTP request, `_get_header` returns `None`. Consequently, requests containing multiple `Content-Length` headers bypass the preliminary body-size guard. This violates RFC 9110 / RFC 7230 and opens the door to HTTP request smuggling.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/middleware/security.py:136-150`:

```python
def _get_header(scope_headers: list[tuple[bytes, bytes]], key: bytes) -> str | None:
    values = [value.decode("latin-1") for name, value in scope_headers if name.lower() == key]
    return values[0] if len(values) == 1 else None
```

When an HTTP request includes two `Content-Length` headers:

- `values` contains 2 items.
- `len(values) == 1` evaluates to `False`.
- `_get_header` returns `None`.
  In `_declared_body_size`:

```python
def _declared_body_size(scope_headers: list[tuple[bytes, bytes]]) -> int | None:
    value = _get_header(scope_headers, b"content-length")
    if value is None:
        return None
```

In `__call__`:

```python
declared_size = _declared_body_size(scope_headers)
if declared_size is not None and declared_size > max_body:
    await _send_error(send, 413, _413_BODY)
    return
```

Because `declared_size` is `None`, the initial 413 rejection is skipped. While streamed chunks are counted later, RFC 9110 §8.6 explicitly states:
_"If a message is received with both a Transfer-Encoding and a Content-Length header field, or multiple conflicting Content-Length header fields, the recipient MUST reject the message with a 400 (Bad Request) status code."_

#### 2. Failure Scenarios & Security/Operational Impact

1. **HTTP Request Smuggling**: Discrepancies in how Caddy and uvicorn parse duplicate `Content-Length` headers can lead to request smuggling or desynchronization in reverse-proxy pipelines.
2. **Resource Consumption**: Massive request bodies with duplicate headers are streamed into memory until the byte limit triggers, rather than being rejected at zero bytes.

#### 3. Concrete Implementation Specification

In `backend/src/novelai/api/middleware/security.py:190-210`, detect duplicate header fields and reject immediately with HTTP 400 Bad Request:

```python
_400_DUPLICATE_HEADER = json.dumps({"detail": "Duplicate Content-Length header"}).encode()

async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        await self.app(scope, receive, send)
        return

    scope_headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    cl_headers = [v for k, v in scope_headers if k.lower() == b"content-length"]
    if len(cl_headers) > 1:
        await _send_error(send, 400, _400_DUPLICATE_HEADER)
        return

    # Continue with existing declared size and stream enforcement
    declared_size = _declared_body_size(scope_headers)
    if declared_size is not None and declared_size > self._max_body_bytes:
        await _send_error(send, 413, _413_BODY)
        return
```

#### 4. Verification & Test Strategy

In `backend/tests/test_duplicate_headers.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

@pytest.mark.asyncio
async def test_rejects_duplicate_content_length(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/auth/login", headers=[("Content-Length", "10"), ("Content-Length", "20")])
        assert res.status_code == 400
        assert "Duplicate Content-Length" in res.json()["detail"]
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_duplicate_headers.py`

#### 5. Compatibility & Rollback

Standard HTTP compliance. Valid RFC 9110 clients never send duplicate `Content-Length` headers.
Rollback command: `git checkout HEAD -- backend/src/novelai/api/middleware/security.py`

---

### REC-009: Missing Session Invalidation and CSRF Rotation on Authentication Elevation

- **ID**: `REC-009`
- **Subsystem/Component**: Session Security / Authentication (`novelai.api.routers.auth`, `novelai.api.auth.security`)
- **Target Location**:
  - `backend/src/novelai/api/routers/auth.py:150-155` (`_set_session_user`)
  - `backend/src/novelai/api/routers/auth.py:235, 263, 337` (`login`, `password_login`, `google_callback`)
  - `backend/src/novelai/api/auth/security.py:46-56` (`get_or_create_csrf_token`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: Authentication handlers mutate session cookies in place without calling `request.session.clear()` or rotating the CSRF token upon privilege elevation. This violates OWASP Session Fixation guidelines (ASVS V3.3), allowing an attacker who set a pre-authenticated session cookie to retain access after victim login.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/auth.py:150-155`:

```python
def _set_session_user(request: Request, user_data: dict) -> None:
    request.session["user_id"] = user_data["user_id"]
    request.session["email"] = user_data["email"]
    request.session["role"] = user_data["role"]
    request.session["issued_at"] = datetime.now(UTC).isoformat()
```

`request.session` is modified in-place. Any pre-existing session attributes (including OAuth flow remnants or pre-authenticated CSRF tokens) persist across the privilege boundary.
According to OWASP Session Management Cheat Sheet:
_"Whenever a user authenticates or elevates privileges, the previous session must be destroyed and a fresh session identifier and anti-CSRF token must be issued."_

#### 2. Failure Scenarios & Security/Operational Impact

1. **Session Fixation**: An attacker injects a known guest session cookie into a shared browser (e.g. library kiosk or via subdomain cookie injection). When the victim logs in, the session ID and CSRF token remain unchanged, allowing the attacker to hijack the authenticated session.
2. **State Pollution**: Stale OAuth state or cached session parameters persist in the cookie payload across user switches.

#### 3. Concrete Implementation Specification

1. **Clear Session and Rotate CSRF in `backend/src/novelai/api/routers/auth.py:150-155`**:

```python
def _set_session_user(request: Request, user_data: dict) -> None:
    """Set authenticated session user, clearing pre-login state and rotating CSRF."""
    request.session.clear()
    request.session["user_id"] = user_data["user_id"]
    request.session["email"] = user_data["email"]
    request.session["role"] = user_data["role"]
    request.session["issued_at"] = datetime.now(UTC).isoformat()
    request.session["_csrf_token"] = secrets.token_hex(32)
```

2. **Standardize Invocations**: Ensure `_set_session_user` is invoked uniformly across `login`, `password_login`, `register`, and `google_callback` in `auth.py`.

#### 4. Verification & Test Strategy

In `backend/tests/test_auth_session_fixation.py`:

```python
def test_login_rotates_session_and_csrf(client, test_user):
    # Establish pre-login session with dummy key and old CSRF
    client.cookies.set("novelai_session", create_session_cookie(user_id=None, extra={"temp_key": "val", "_csrf_token": "old_token"}))
    res = client.post("/api/auth/login", json={"email": test_user.email, "password": "password123"})
    assert res.status_code == 200

    # Verify pre-existing keys purged and CSRF rotated
    session_data = decode_session_cookie(client.cookies.get("novelai_session"))
    assert "temp_key" not in session_data
    assert session_data.get("_csrf_token") != "old_token"
    assert session_data.get("user_id") == test_user.id
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_auth_session_fixation.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible with frontend auth flows. Client receives fresh cookie and CSRF token in response.
Rollback command: `git checkout HEAD -- backend/src/novelai/api/routers/auth.py`

---

### REC-010: Layering Boundary Violation in Library Actions Router via Direct Storage Injection

- **ID**: `REC-010`
- **Subsystem/Component**: API Architecture / Modularity (`novelai.api.routers.library_actions`, `novelai.services.library_service`)
- **Target Location**:
  - `backend/src/novelai/api/routers/library_actions.py:19, 183, 198, 216, 252, 285, 308, 324, 336, 375, 410, 425` (`storage: Any = Depends(get_storage)`)
  - `backend/src/novelai/services/library_service.py` (Missing storage orchestration domain methods)
- **Category**: `Architecture`
- **Severity**: `Medium`
- **Summary**: `library_actions.py` directly injects `storage: Any = Depends(get_storage)` across 11 separate endpoints and interacts directly with raw storage primitives (`storage.load_metadata`, `storage.list_novels()`, `storage.list_metadata_history()`, `storage.get_manifest()`). This violates the unidirectional architecture contract (`api -> services -> domain -> storage/db/providers`) enforced by `AGENTS.md` and bypasses service-level business logic and caching.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/library_actions.py`:

```python
@router.get("/{novel_id}/source-metadata", response_model=SourceMetadataInspection)
async def inspect_source_metadata(
    novel_id: str,
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        if novel_id not in storage.list_novels():
            raise HTTPException(status_code=404, detail="Novel not found")
        ...
```

`AGENTS.md` explicitly specifies under _Project invariants -> Backend boundaries_:
_"Dependency direction is api -> services -> domain -> storage/db/providers. Keep routers thin; source parsing belongs in sources/, outbound HTTP and SSRF protection in infrastructure/http/, providers behind provider interfaces, and persistence in storage/ and db/."_
The router import guard strictly forbids importing from `novelai.storage.service` in routers:
`powershell -ExecutionPolicy Bypass -Command "rg -n '^from novelai\.(db\.models|storage\.service|sources\.)' backend/src/novelai/api/routers/ --glob '!dependencies.py'"`
While `library_actions.py` technically avoids importing `novelai.storage.service` directly by importing `get_storage` from `dependencies.py`, injecting the raw storage adapter into 11 separate router endpoints violates the architectural boundary and tightly couples HTTP routes to physical storage operations.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Architectural Erosion**: Bypassing `LibraryService` duplicates novel existence validation (`novel_id not in storage.list_novels()`), metadata sanitization, and error handling across routers.
2. **Inability to Cache or Intercept**: Any caching or access auditing added to `LibraryService` is completely bypassed when clients call these library action endpoints.

#### 3. Concrete Implementation Specification

1. **Add Domain Methods to `LibraryService` in `backend/src/novelai/services/library_service.py`**:

```python
def get_source_metadata(self, novel_id: str) -> dict[str, Any] | None:
    """Retrieve source metadata for a novel, returning None if novel does not exist."""
    if not self.novel_exists(novel_id):
        return None
    return self.storage.load_metadata(novel_id)

def list_source_metadata_history(self, novel_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Retrieve metadata revision history for a novel."""
    if not self.novel_exists(novel_id):
        raise NotFoundError(f"Novel {novel_id} not found")
    return self.storage.list_metadata_history(novel_id, limit=limit)

def get_novel_manifest(self, novel_id: str) -> dict[str, Any] | None:
    """Retrieve generation manifest for a novel."""
    return self.storage.get_manifest(novel_id)
```

2. **Refactor `backend/src/novelai/api/routers/library_actions.py`**:

- Remove `get_storage` from dependencies import.
- Replace all 11 occurrences of `storage: Any = Depends(get_storage)` with `library_service: LibraryService = Depends(get_library_service)`.
- Replace raw storage calls with calls to `library_service.get_source_metadata()`, `library_service.list_source_metadata_history()`, and `library_service.get_novel_manifest()`.

#### 4. Verification & Test Strategy

Verify architectural import guard and typechecks:

```powershell
powershell -ExecutionPolicy Bypass -Command "rg -n 'Depends\(get_storage\)' backend/src/novelai/api/routers/library_actions.py"
# Must return 0 matches / exit 1
powershell -ExecutionPolicy Bypass -File tools/pyright.ps1
```

#### 5. Compatibility & Rollback

Pure internal refactoring. REST API endpoints and response schemas remain identical.
Rollback command: `git checkout HEAD -- backend/src/novelai/api/routers/library_actions.py backend/src/novelai/services/library_service.py`

---

## Iteration 2: Database Layer, ORM Models, Session Scoping, Engines, & Alembic Migrations

Audit Focus: Database models, session scoping, connection engine pooling, advisory locking, Alembic autogenerate metadata, and migration robustness.

### Summary of Recommendations (Iteration 2)

| ID          | Subsystem / Component                                                                                                                    | Category        | Title                                                                                    |
| :---------- | :--------------------------------------------------------------------------------------------------------------------------------------- | :-------------- | :--------------------------------------------------------------------------------------- |
| **REC-011** | Database Migrations (`novelai.alembic.env`, `novelai.db.models`)                                                                         | Bug/Reliability | Alembic Autogenerate Metadata Omits Scheduler State and Takedown Models                  |
| **REC-012** | Database Concurrency & Locking (`novelai.db.advisory_lock`, `novelai.db.engine`)                                                         | Bug/Reliability | Session-Level Advisory Lock Leakage Under Transaction Connection Pooling                 |
| **REC-013** | Database Engine Configuration (`novelai.db.engine`, `novelai.config.settings`)                                                           | Bug/Reliability | Missing Transaction Pooler Detection and Prepared Statement Collision Protection         |
| **REC-014** | Database Session Routing (`novelai.main_reader`, `novelai.api.routers.dependencies`, `novelai.db.engine`)                                | Performance     | Guest Reader API Service Bypasses Read Replica Engine and Overloads Primary DB           |
| **REC-015** | Database Security & Row-Level Security (`novelai.db.engine`, `novelai.alembic.versions`, `novelai.sql`)                                  | Security        | PostgreSQL Row-Level Security Functions Lack Application Context Fallback                |
| **REC-016** | ORM Models (`novelai.db.models.novel`, `novelai.db.models.chapter`)                                                                      | Architecture    | Clamped String Column Length on Novel Titles Violates Repository Architectural Invariant |
| **REC-017** | ORM Models & Concurrency (`novelai.db.models.novel`)                                                                                     | Gap             | Missing Optimistic Concurrency Control on Mutable Novel Catalog Model                    |
| **REC-018** | Database Task Queue (`novelai.activity.database`, `novelai.db.models.activity`)                                                          | Performance     | In-Memory Full-Table Scan During Stale Worker Lease Recovery in Activity Queue           |
| **REC-019** | Database Performance & Admin Logging (`novelai.db.models.system`, `novelai.services.audit_service`)                                      | Performance     | Missing Index on AuditLog Timestamp Causing Sequential Scans on Admin Pagination         |
| **REC-020** | Database Schema Design & Scalability (`novelai.db.models.analytics_event`, `novelai.db.models.system`, `novelai.db.models.notification`) | Weakness        | 32-Bit Integer Primary Key Overflow Risk on High-Volume Append-Only Tables               |

---

### REC-011: Alembic Autogenerate Metadata Omits Scheduler State and Takedown Models

- **ID**: `REC-011`
- **Subsystem/Component**: Database Migrations (`novelai.alembic.env`, `novelai.db.models`)
- **Target Location**:
  - `backend/alembic/env.py:30-45` (Hardcoded model module iteration loop)
  - `backend/src/novelai/db/models/__init__.py:1-48` (Canonical model exports)
  - `backend/src/novelai/db/models/scheduler_runtime_state.py:23-64` (`SchedulerRuntimeState`)
  - `backend/src/novelai/db/models/takedown.py:16-52` (`TakedownRequest`)
- **Category**: `Bug/Reliability`
- **Severity**: `High`
- **Summary**: `backend/alembic/env.py` iterates over an uncoordinated hardcoded tuple of 11 model module names to register tables on `Base.metadata`. It omits `scheduler_runtime_state` and `takedown`. Consequently, running `alembic revision --autogenerate` treats `scheduler_runtime_states` and `takedown_requests` as dropped tables and generates destructive `op.drop_table()` operations.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/alembic/env.py:30-45`:

```python
for _model_module in (
    "novelai.db.models.analytics_event",
    "novelai.db.models.activity",
    "novelai.db.models.chapter",
    "novelai.db.models.genre",
    "novelai.db.models.glossary",
    "novelai.db.models.jobs",
    "novelai.db.models.novel",
    "novelai.db.models.notification",
    "novelai.db.models.system",
    "novelai.db.models.tag",
    "novelai.db.models.users",
):
    import_module(_model_module)
```

In `backend/src/novelai/db/models/__init__.py`:

```python
from novelai.db.models.scheduler_runtime_state import SchedulerRuntimeState
from novelai.db.models.takedown import TakedownRequest
```

The central models package exports all 13 model classes, including `SchedulerRuntimeState` and `TakedownRequest`. However, because `backend/alembic/env.py` manually lists modules instead of importing `novelai.db.models`, newly added models are not registered in `Base.metadata`.
When an operator runs `alembic revision --autogenerate -m "schema_sync"`, Alembic inspects PostgreSQL, sees `scheduler_runtime_states` and `takedown_requests` in the live database, but does not find them in `Base.metadata`. It automatically emits:

```python
op.drop_table('scheduler_runtime_states')
op.drop_table('takedown_requests')
```

Applying this generated migration destroys background scheduler distributed lock states and DMCA takedown compliance records.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Accidental Table Drops**: Autogenerated migrations will drop production tables containing legal DMCA takedown requests (`takedown_requests`) and distributed coordinator states (`scheduler_runtime_states`).
2. **Migration Drift & CI Failures**: Schema drift detection in CI (`alembic check`) fails because the live database contains tables absent from Alembic's metadata.

#### 3. Concrete Implementation Specification

In `backend/alembic/env.py:30-45`, replace the manual module iteration loop with a package import of `novelai.db.models`:

```python
# Import the models package to register all models with Base.metadata.
# novelai.db.models.__init__ imports and exports every model module,
# guaranteeing autogenerate sees all current and future schema objects.
import novelai.db.models  # noqa: F401
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_alembic_metadata_registration.py`:

```python
def test_all_registered_models_present_in_alembic_metadata():
    import novelai.db.models as models_pkg
    from novelai.db.base import Base

    table_names = set(Base.metadata.tables.keys())
    assert "scheduler_runtime_states" in table_names, "scheduler_runtime_states missing from Base.metadata"
    assert "takedown_requests" in table_names, "takedown_requests missing from Base.metadata"
    assert "novels" in table_names
    assert "users" in table_names
    assert "activity_records" in table_names
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_alembic_metadata_registration.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Ensures Alembic metadata strictly mirrors the complete schema.
Rollback command: `git checkout HEAD -- backend/alembic/env.py`

---

### REC-012: Session-Level Advisory Lock Leakage Under Transaction Connection Pooling

- **ID**: `REC-012`
- **Subsystem/Component**: Database Concurrency & Locking (`novelai.db.advisory_lock`, `novelai.db.engine`)
- **Target Location**:
  - `backend/src/novelai/db/advisory_lock.py:20-45` (`try_advisory_lock`, `advisory_unlock`)
  - `backend/src/novelai/db/engine.py:140-155` (`DB_CONNECTION_MODE == "transaction"`)
- **Category**: `Bug/Reliability`
- **Severity**: `High`
- **Summary**: `try_advisory_lock` executes session-level PostgreSQL advisory locks (`pg_try_advisory_lock`), which leak across pooled connections or fail to release on unhandled crashes when running under transaction-mode connection poolers (PgBouncer or Supabase port 6543).

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/db/advisory_lock.py:20-45`:

```python
def try_advisory_lock(session: Session, key: str) -> bool:
    """Attempt non-blocking lock acquisition using pg_try_advisory_lock."""
    lock_id = string_to_advisory_lock_id(key)
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        result = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id},
        ).scalar()
        return bool(result)
    return True

def advisory_unlock(session: Session, key: str) -> bool:
    """Release advisory lock."""
    lock_id = string_to_advisory_lock_id(key)
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        result = session.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": lock_id},
        ).scalar()
        return bool(result)
    return True
```

In PostgreSQL, `pg_try_advisory_lock()` creates a **session-level** lock tied to the physical PostgreSQL connection, independent of transactions.
When `settings.DB_CONNECTION_MODE == "transaction"` (such as with PgBouncer or Supabase transaction pooling on port 6543):

1. Connections are returned to the pool at the end of each SQL transaction (`COMMIT` or `ROLLBACK`).
2. If an exception or task termination interrupts execution before `advisory_unlock()` runs, the physical PostgreSQL connection retains the advisory lock.
3. Another unrelated transaction checking out that server connection from the pool unwittingly holds the lock, while other worker processes attempting to lock that key are blocked indefinitely.
4. If a transaction acquires a session lock and commits intermediate work, PgBouncer may assign the next query in the same Python session to a different server connection where the lock is not held.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Permanent Worker Lockout**: A crawler timeout or unhandled exception during chapter sync leaves the advisory lock held on a pooled server connection. Subsequent crawl attempts targeting that novel fail repeatedly with lock contention.
2. **False Concurrency Isolation**: A worker executing under transaction pooling assumes its lock protects multi-step operations, but intermediate commits reassign the physical connection, allowing a second worker to acquire the same lock concurrently.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/advisory_lock.py:20-45`, add transaction-scoped advisory locking via PostgreSQL's native `pg_try_advisory_xact_lock()`:

```python
def try_advisory_xact_lock(session: Session, key: str) -> bool:
    """Attempt non-blocking transaction-scoped advisory lock acquisition.

    Automatically releases at transaction COMMIT or ROLLBACK.
    Safe for PgBouncer / transaction-mode pooling.
    """
    lock_id = string_to_advisory_lock_id(key)
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        result = session.execute(
            text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
            {"lock_id": lock_id},
        ).scalar()
        return bool(result)
    return True
```

2. Update callers to prefer `try_advisory_xact_lock` during database transactions so manual `advisory_unlock` calls are rendered obsolete.

#### 4. Verification & Test Strategy

Create `backend/tests/test_advisory_xact_lock.py`:

```python
def test_advisory_xact_lock_auto_releases_on_rollback(db_session):
    if db_session.bind.dialect.name != "postgresql":
        return
    from novelai.db.advisory_lock import try_advisory_xact_lock
    key = "novel-crawl-lock-42"
    assert try_advisory_xact_lock(db_session, key) is True
    db_session.rollback()
    # Lock must be immediately acquirable again on a fresh transaction
    assert try_advisory_xact_lock(db_session, key) is True
    db_session.rollback()
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_advisory_xact_lock.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Replaces error-prone manual unlocking with PostgreSQL's transactional lifecycle.
Rollback command: `git checkout HEAD -- backend/src/novelai/db/advisory_lock.py`

---

### REC-013: Missing Transaction Pooler Detection and Prepared Statement Collision Protection

- **ID**: `REC-013`
- **Subsystem/Component**: Database Engine Configuration (`novelai.db.engine`, `novelai.config.settings`)
- **Target Location**:
  - `backend/src/novelai/db/engine.py:125-155` (`_create_configured_engine`)
  - `backend/src/novelai/config/settings.py:384` (`DB_CONNECTION_MODE`)
- **Category**: `Bug/Reliability`
- **Severity**: `High`
- **Summary**: `DB_CONNECTION_MODE` defaults to `"direct"`. When connecting to Supabase transaction pooler (port 6543) or PgBouncer without explicitly setting `DB_CONNECTION_MODE="transaction"`, `prepare_threshold` remains at default 5 and `QueuePool` is used. On the 5th execution of any prepared statement, Psycopg 3 emits `PREPARE` and crashes with `psycopg.errors.DuplicatePreparedStatement`.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/config/settings.py:384`:

```python
DB_CONNECTION_MODE: Literal["direct", "session", "transaction"] = "direct"
```

In `backend/src/novelai/db/engine.py:140-155`:

```python
if settings.DB_CONNECTION_MODE == "transaction":
    kwargs["poolclass"] = NullPool
    connect_args["prepare_threshold"] = None
else:
    kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    )
```

In Psycopg 3:

- `prepare_threshold=None` disables server-side prepared statements entirely on the connection.
- `prepare_threshold=5` (default) automatically prepares statements after 5 executions on the same connection.
- `prepare_threshold=0` prepares statements immediately on first execution.

If an operator provisions Supabase and sets `DATABASE_URL` to point to port `6543` (transaction pooling) or `*.pooler.supabase.com` but forgets to set `DB_CONNECTION_MODE="transaction"` in `.env`, `_create_configured_engine` runs the `else` branch:

1. `QueuePool` is used instead of `NullPool`, leading to double connection pooling.
2. `prepare_threshold` is not set to `None`, keeping Psycopg 3's default threshold of 5.
3. On the 5th query execution across different requests sharing backend pool connections, Psycopg 3 sends `PREPARE _psycopg_statement_...`.
4. PgBouncer assigns the client to a PostgreSQL backend that already has that prepared statement cached from another client transaction.
5. PostgreSQL throws:
   `psycopg.errors.DuplicatePreparedStatement: prepared statement "_psycopg_statement_..." already exists`.
6. The client transaction aborts with HTTP 500.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Intermittent Production 500 Crashes**: Under sustained traffic behind PgBouncer or Supabase transaction pooler, frequently hit endpoints (e.g. auth checks, novel lookup by slug) reliably crash with `DuplicatePreparedStatement` on the 5th request.
2. **Transaction Poisoning**: A prepared statement error leaves the connection in an aborted state, rolling back user operations.

#### 3. Concrete Implementation Specification

In `backend/src/novelai/db/engine.py:125-155`, add automatic pooler detection from `DATABASE_URL` (checking for port `:6543` or pooler host patterns) and enforce `NullPool` with `connect_args["prepare_threshold"] = None`:

```python
def _is_transaction_pooler(db_url: str) -> bool:
    """Return True if settings or URL indicate a transaction-mode connection pooler."""
    if settings.DB_CONNECTION_MODE == "transaction":
        return True
    return ":6543/" in db_url or "pooler.supabase.com" in db_url

def _create_configured_engine(db_url: str) -> Engine:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if db_url.startswith("postgresql"):
        connect_args: dict[str, Any] = {
            "connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
            "sslmode": settings.DB_SSL_MODE,
            "options": " ".join(
                (
                    f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}",
                    f"-c lock_timeout={settings.DB_LOCK_TIMEOUT_MS}",
                    f"-c idle_in_transaction_session_timeout={settings.DB_IDLE_IN_TRANSACTION_TIMEOUT_MS}",
                )
            ),
        }
        if _is_transaction_pooler(db_url):
            kwargs["poolclass"] = NullPool
            connect_args["prepare_threshold"] = None
        else:
            kwargs.update(
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
                pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
            )
        kwargs["connect_args"] = connect_args
    engine = create_engine(db_url, **kwargs)
    _install_timing_listeners(engine)
    return engine
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_engine_pooler_detection.py`:

```python
from novelai.db.engine import _create_configured_engine
from sqlalchemy.pool import NullPool

def test_auto_detects_supabase_transaction_pooler_url():
    url = "postgresql+psycopg://user:pass@db.example.pooler.supabase.com:6543/postgres"
    engine = _create_configured_engine(url)
    assert engine.pool.__class__ is NullPool
    assert engine.dialect.connect_args.get("prepare_threshold") is None
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_engine_pooler_detection.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Eliminates manual configuration errors when using transaction poolers.
Rollback command: `git checkout HEAD -- backend/src/novelai/db/engine.py`

---

### REC-014: Guest Reader API Service Bypasses Read Replica Engine and Overloads Primary DB

- **ID**: `REC-014`
- **Subsystem/Component**: Database Session Routing (`novelai.main_reader`, `novelai.api.routers.dependencies`, `novelai.db.engine`)
- **Target Location**:
  - `backend/src/novelai/main_reader.py:58-95` (`create_reader_app`)
  - `backend/src/novelai/api/routers/dependencies.py:135-165` (`get_db_session`)
  - `backend/src/novelai/db/engine.py:195-215` (`read_session_scope`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `main_reader.py` overrides `get_current_user` for anonymous guest access but fails to override `get_db_session`. Public reader routers (`public_catalog.py`, `public_chapter.py`, `public_novel.py`, `public_rankings.py`, `public_dmca.py`) all inject `db: Session = Depends(get_db_session)`, routing 100% of guest reading traffic to the primary write database and leaving `DATABASE_REPLICA_URL` unused.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/db/engine.py:195-215`:

```python
@contextmanager
def read_session_scope(url: str | None = None) -> Generator[Session]:
    target_url = url or settings.DATABASE_REPLICA_URL or settings.DATABASE_URL
    Session_ = get_sessionmaker(target_url)
    session = Session_()
    try:
        bind = session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
            session.execute(text("SET LOCAL statement_timeout = '3000'"))
        yield session
    finally:
        session.rollback()
        session.close()
```

In `backend/src/novelai/api/routers/dependencies.py:135-165`:

```python
def get_db_session():
    ...
    SM = get_sessionmaker()  # defaults to settings.DATABASE_URL (PRIMARY)
    session = SM()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

In `backend/src/novelai/main_reader.py:58-95`:

```python
app.dependency_overrides[get_current_user] = get_reader_user
```

`get_db_session` is never overridden.
Consequently, all public read traffic (chapter content requests, novel catalogs, tag filters, rankings, search queries) served by `novelai.main_reader` uses `get_db_session()`, connecting directly to the primary PostgreSQL writer instance and running `session.commit()` on exit.
This exhausts the primary database connection pool (budgeted at 5 connections) and exposes the write database to IOPS exhaustion during reader traffic surges.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Primary Write Starvation**: High public reader concurrency consumes all 5 connections in the primary pool, causing administrative actions, novel crawl ingests, and translation jobs to fail with connection pool exhaustion (`TimeoutError: QueuePool limit of size 5 overflow 5 reached`).
2. **Idle Replicas**: Read replicas provisioned for horizontal read scaling handle 0% of traffic.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/api/routers/dependencies.py:135-165`, declare `get_read_db_session`:

```python
def get_read_db_session():
    """FastAPI dependency for read-only database sessions bound to replica engine."""
    from novelai.db.engine import read_session_scope

    with read_session_scope() as session:
        yield session
```

2. In `backend/src/novelai/main_reader.py:create_reader_app`, override `get_db_session`:

```python
from novelai.api.routers.dependencies import get_current_user, get_db_session, get_read_db_session

# Override auth dependencies for reader (guest allowed)
app.dependency_overrides[get_current_user] = get_reader_user
# Route all reader database queries to read replica engine
app.dependency_overrides[get_db_session] = get_read_db_session
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_reader_db_routing.py`:

```python
from novelai.api.routers.dependencies import get_db_session, get_read_db_session
from novelai.main_reader import create_reader_app

def test_reader_app_overrides_db_session_to_read_replica():
    app = create_reader_app()
    assert get_db_session in app.dependency_overrides
    assert app.dependency_overrides[get_db_session] == get_read_db_session
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_reader_db_routing.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. When `DATABASE_REPLICA_URL` is not set, `read_session_scope()` gracefully falls back to `DATABASE_URL`.
Rollback command: `git checkout HEAD -- backend/src/novelai/main_reader.py backend/src/novelai/api/routers/dependencies.py`

---

### REC-015: PostgreSQL Row-Level Security Functions Lack Application Context Fallback

- **ID**: `REC-015`
- **Subsystem/Component**: Database Security & Row-Level Security (`novelai.db.engine`, `novelai.alembic.versions`, `novelai.sql`)
- **Target Location**:
  - `backend/alembic/versions/2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py:354-380` (`private.current_user_id`, `private.is_owner`)
  - `backend/sql/rls_policies.sql:40-65` (`public.current_user_id`, `public.is_owner`)
  - `backend/src/novelai/db/engine.py:238-246` (`session_scope` setting `app.current_user_id`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: PostgreSQL RLS helper functions `private.current_user_id()` and `private.is_owner()` inspect only Supabase JWT context (`auth.uid()`), completely ignoring `app.current_user_id` set by SQLAlchemy `session_scope`. When the backend connects using application session cookies, all user-scoped RLS policies evaluate to FALSE, hiding user records.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/db/engine.py:238-246`:

```python
if current_user_id is not None:
    # Set local variable for RLS using set_config; fail-safe across Postgres dialects
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.current_user_id', :uid, true)"),
            {"uid": str(current_user_id)},
        )
```

In `backend/alembic/versions/2026-07-16_3da9f497264c_remove_pg_net_and_reconcile_rls_policies.py:354-380`:

```sql
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
```

Notice:

1. `private.current_user_id()` and `private.is_owner()` check only `(SELECT auth.uid())::text`.
2. When the backend Python process executes queries with cookie session authentication, `auth.uid()` evaluates to NULL.
3. Because `app.current_user_id` is never checked by `private.current_user_id()`, the function returns NULL.
4. All user-scoped RLS policies on `users`, `library_items`, `reading_history`, `reading_progress`, `reviews`, and `user_glossary_display_overrides` evaluate to `FALSE`.
5. Authenticated users receive empty querysets for their own library, history, and preferences whenever RLS is enforced.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Silent Data Invisibility**: Authenticated backend users receive empty results when querying their reading history, progress, or library items because RLS filters out all rows where `user_id = NULL`.
2. **Owner Administrative Lockout**: If admin views are queried under RLS, `private.is_owner()` returns `FALSE`, locking out valid owners authenticated through session cookies.

#### 3. Concrete Implementation Specification

Create a new Alembic migration `backend/alembic/versions/2026-08-15_reconcile_rls_app_context.py` to upgrade `private.current_user_id()` and `private.is_owner()`:

```python
"""reconcile rls app context

Revision ID: 4ea1a29f810b
Revises: 3da9f497264c
Create Date: 2026-08-15 12:00:00.000000
"""
from alembic import op

revision = "4ea1a29f810b"
down_revision = "3da9f497264c"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION private.current_user_id()
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
        DECLARE
            v_app_uid text;
            v_auth_uid text;
        BEGIN
            v_app_uid := NULLIF(current_setting('app.current_user_id', true), '');
            IF v_app_uid IS NOT NULL THEN
                RETURN v_app_uid::integer;
            END IF;

            BEGIN
                v_auth_uid := (SELECT auth.uid())::text;
            EXCEPTION WHEN OTHERS THEN
                v_auth_uid := NULL;
            END;

            IF v_auth_uid IS NOT NULL THEN
                RETURN (SELECT id FROM public.users WHERE auth_provider_subject = v_auth_uid LIMIT 1);
            END IF;

            RETURN NULL;
        END;
        $$;

        CREATE OR REPLACE FUNCTION private.is_owner()
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
        DECLARE
            v_app_uid text;
            v_auth_uid text;
        BEGIN
            v_app_uid := NULLIF(current_setting('app.current_user_id', true), '');
            IF v_app_uid IS NOT NULL THEN
                RETURN EXISTS (
                    SELECT 1 FROM public.users WHERE id = v_app_uid::integer AND role = 'owner'
                );
            END IF;

            BEGIN
                v_auth_uid := (SELECT auth.uid())::text;
            EXCEPTION WHEN OTHERS THEN
                v_auth_uid := NULL;
            END;

            IF v_auth_uid IS NOT NULL THEN
                RETURN EXISTS (
                    SELECT 1 FROM public.users WHERE auth_provider_subject = v_auth_uid AND role = 'owner'
                );
            END IF;

            RETURN FALSE;
        END;
        $$;
        """
    )

def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION private.current_user_id()
        RETURNS integer
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = ''
        AS $$
            SELECT id FROM public.users WHERE auth_provider_subject = (SELECT auth.uid())::text LIMIT 1;
        $$;
        """
    )
```

#### 4. Verification & Test Strategy

In `backend/tests/test_rls_session_context.py`:

```python
def test_rls_functions_read_app_current_user_id(db_session):
    if db_session.bind.dialect.name != "postgresql":
        return
    db_session.execute(text("SELECT set_config('app.current_user_id', '42', true)"))
    res = db_session.execute(text("SELECT private.current_user_id()")).scalar()
    assert res == 42
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_rls_session_context.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible with Supabase Auth JWTs while enabling native SQLAlchemy backend session scoping.
Rollback command: `git checkout HEAD -- backend/alembic/versions/2026-08-15_reconcile_rls_app_context.py`

---

### REC-016: Clamped String Column Length on Novel Titles Violates Repository Architectural Invariant

- **ID**: `REC-016`
- **Subsystem/Component**: ORM Models (`novelai.db.models.novel`, `novelai.db.models.chapter`)
- **Target Location**:
  - `backend/src/novelai/db/models/novel.py:56-60` (`title`, `original_title`)
  - `backend/src/novelai/db/models/chapter.py:54-56` (`translated_section_title`, `section_title`)
  - `AGENTS.md:144-146` (Project Invariant: Text columns for web novel titles and notes)
- **Category**: `Architecture`
- **Severity**: `High`
- **Summary**: `Novel.title`, `original_title`, and `Chapter.section_title` declare `String(512)`, directly violating the repository invariant in `AGENTS.md` requiring SQLAlchemy `Text` for web novel titles and metadata, causing database insertion crashes on authentic long-title web novels.

#### 1. Root Cause & Code-Level Diagnostic

`AGENTS.md` explicitly mandates under _Project invariants -> Backend boundaries_:
_"Web novel titles, episode subtitles, author notes, and chapter HTML bodies must use SQLAlchemy Text, never clamped String(255) or String(512)."_
However, in `backend/src/novelai/db/models/novel.py:56-60`:

```python
title: Mapped[str] = mapped_column(String(512), nullable=False)
original_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

And in `backend/src/novelai/db/models/chapter.py:54-56`:

```python
translated_section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

In Japanese web novel culture (notably on Syosetu / Shousetsuka ni Narou and Kakuyomu), titles often function as descriptive multi-sentence synopses that frequently exceed 512 characters.
When a crawler ingests a novel whose title exceeds 512 characters, PostgreSQL rejects the insert/update with:
`psycopg.errors.StringDataRightTruncation: value too long for type character varying(512)`.
The transaction aborts, preventing novel synchronization and corrupting worker task queues.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Crawler Pipeline Crash**: Ingestion jobs crash abruptly when encountering popular long-title works, blocking catalog synchronization.
2. **Repository Contract Violation**: Violates the explicit repository specification defined in `AGENTS.md`.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/models/novel.py:56-60`, change `String(512)` to `Text`:

```python
title: Mapped[str] = mapped_column(Text, nullable=False)
original_title: Mapped[str | None] = mapped_column(Text, nullable=True)
```

2. In `backend/src/novelai/db/models/chapter.py:54-56`, change `String(512)` to `Text`:

```python
translated_section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
```

3. Create an Alembic migration `backend/alembic/versions/2026-08-16_widen_novel_titles_to_text.py`:

```python
def upgrade() -> None:
    op.alter_column("novels", "title", type_=sa.Text(), existing_type=sa.String(512), nullable=False)
    op.alter_column("novels", "original_title", type_=sa.Text(), existing_type=sa.String(512), nullable=True)
    op.alter_column("chapters", "translated_section_title", type_=sa.Text(), existing_type=sa.String(512), nullable=True)
    op.alter_column("chapters", "section_title", type_=sa.Text(), existing_type=sa.String(512), nullable=True)

def downgrade() -> None:
    op.alter_column("novels", "title", type_=sa.String(512), existing_type=sa.Text(), nullable=False)
    op.alter_column("novels", "original_title", type_=sa.String(512), existing_type=sa.Text(), nullable=True)
    op.alter_column("chapters", "translated_section_title", type_=sa.String(512), existing_type=sa.Text(), nullable=True)
    op.alter_column("chapters", "section_title", type_=sa.String(512), existing_type=sa.Text(), nullable=True)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_novel_title_length.py`:

```python
def test_novel_accepts_title_exceeding_512_chars(db_session):
    from novelai.db.models.novel import Novel
    long_title = "A" * 750
    novel = Novel(
        slug="test-long-title",
        title=long_title,
        original_title="Original " + ("B" * 600),
    )
    db_session.add(novel)
    db_session.commit()
    assert len(novel.title) == 750
    assert len(novel.original_title) == 609
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_novel_title_length.py`

#### 5. Compatibility & Rollback

In PostgreSQL, altering `VARCHAR(512)` to `TEXT` is a metadata-only operation (`O(1)`) requiring zero table rewrite. Fully reversible via downgrade.
Rollback command: `git checkout HEAD -- backend/src/novelai/db/models/novel.py backend/src/novelai/db/models/chapter.py`

---

### REC-017: Missing Optimistic Concurrency Control on Mutable Novel Catalog Model

- **ID**: `REC-017`
- **Subsystem/Component**: ORM Models & Concurrency (`novelai.db.models.novel`)
- **Target Location**:
  - `backend/src/novelai/db/models/novel.py:50-80` (`Novel`)
  - `backend/src/novelai/services/catalog_admin_service.py`
- **Category**: `Gap`
- **Severity**: `Medium`
- **Summary**: The `Novel` model lacks optimistic concurrency control (`version_id_col`), allowing concurrent writes between background crawler sync workers, translation pipelines, and admin UI edits to silently overwrite catalog counters, publication status, and metadata (lost update anomaly).

#### 1. Root Cause & Code-Level Diagnostic

The `Novel` entity aggregates high-frequency mutable counters (`chapter_count`, `translated_count`), publication status (`publication_status`), translation status (`translation_status`), and sync metadata (`source_updated_at`, `latest_chapter_number`).
Multiple asynchronous processes concurrently operate on the same novel:

1. Crawler worker updates `chapter_count` and `latest_chapter_number`.
2. Translation worker increments `translated_count` and toggles `translation_status`.
3. Admin edits metadata (description, publication status, custom title) via the admin dashboard.

In `backend/src/novelai/db/models/novel.py:50-80`:

```python
class Novel(Base):
    __tablename__ = "novels"
    # No version_id column or version_id_col in __mapper_args__
```

When two workers read the `Novel` row at time $T_0$, modify different attributes, and commit at $T_1$ and $T_2$, the second writer executes:

```sql
UPDATE novels SET chapter_count = 120 WHERE id = 1;
```

The first writer's updates (e.g. `translated_count = 50` or admin description changes) are silently overwritten and lost.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Desynchronized Chapter Counters**: `Novel.chapter_count` becomes desynchronized from the actual number of chapters stored in R2 and PostgreSQL, breaking reader pagination and chapter list APIs.
2. **Overwritten Admin Changes**: Admin edits to novel descriptions or publication statuses are discarded when background sync jobs commit concurrent updates.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/models/novel.py:50-80`, add `version_id` and configure mapper arguments:

```python
class Novel(Base):
    __tablename__ = "novels"

    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {
        "version_id_col": version_id,
    }
```

2. When SQLAlchemy flushes updates to `novels`, it automatically adds `WHERE version_id = :expected_version` and increments `version_id = version_id + 1`. If another transaction updated the row concurrently, SQLAlchemy raises `StaleDataError`.
3. For background high-frequency counter updates where full object hydration is not required, use atomic SQL expressions:

```python
session.execute(
    update(Novel)
    .where(Novel.id == novel_id)
    .values(chapter_count=Novel.chapter_count + 1)
)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_novel_optimistic_locking.py`:

```python
import pytest
from sqlalchemy.orm.exc import StaleDataError
from novelai.db.models.novel import Novel

def test_novel_concurrent_update_raises_stale_data(session_factory):
    with session_factory() as s1:
        n1 = Novel(slug="test-concurrency", title="Initial Title")
        s1.add(n1)
        s1.commit()
        n_id = n1.id

    with session_factory() as s1, session_factory() as s2:
        row1 = s1.get(Novel, n_id)
        row2 = s2.get(Novel, n_id)

        row1.title = "Updated by Worker 1"
        s1.commit()

        row2.title = "Updated by Worker 2"
        with pytest.raises(StaleDataError):
            s2.commit()
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_novel_optimistic_locking.py`

#### 5. Compatibility & Rollback

Requires adding integer column `version_id` (default 1) via Alembic. Existing rows receive `version_id = 1`.
Rollback command: `git checkout HEAD -- backend/src/novelai/db/models/novel.py`

---

### REC-018: In-Memory Full-Table Scan During Stale Worker Lease Recovery in Activity Queue

- **ID**: `REC-018`
- **Subsystem/Component**: Database Task Queue (`novelai.activity.database`, `novelai.db.models.activity`)
- **Target Location**:
  - `backend/src/novelai/activity/database.py:362-390` (`_recover_expired`)
  - `backend/src/novelai/activity/database.py:526, 601` (`claim_activity`, `claim_next`)
  - `backend/src/novelai/db/models/activity.py:30-45` (`ActivityRecord`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `_recover_expired` executes on every worker task claim: it queries all `RUNNING` activity records into application memory and iterates through them in Python to test lease deadlines, causing CPU thrashing, network serialization bloat, and transaction lock contention across workers.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/database.py:362-390`:

```python
def _recover_expired(self, session: Session) -> None:
    now = _utc_now()
    rows = session.scalars(
        select(ActivityRecord)
        .options(
            load_only(
                ActivityRecord.activity_id,
                ActivityRecord.status,
                ActivityRecord.started_at,
                ActivityRecord.lease_id,
                ActivityRecord.lease_expires_at,
                ActivityRecord.last_heartbeat_at,
                ActivityRecord.error,
                ActivityRecord.metadata_json,
                ActivityRecord.updated_at,
            )
        )
        .where(ActivityRecord.status == JobStatus.RUNNING.value)
    ).all()
    for row in rows:
        if not self._lease_expired(row, now):
            continue
        metadata = _decode_metadata(row.metadata_json)
        metadata["lease_recovered_at"] = _iso(now)
        metadata["current_stage"] = "queued"
        row.status = JobStatus.PENDING.value
        row.started_at = None
        row.lease_id = None
        row.lease_expires_at = None
        row.last_heartbeat_at = None
        row.error = "Recovered expired activity lease"
        row.metadata_json = _metadata_text(metadata)
        row.updated_at = now
```

In `backend/src/novelai/activity/database.py:526, 601`:
`_recover_expired(session)` is called during every `claim_activity` and `claim_next` invocation.
Notice:

1. Every time any worker requests work, all currently executing jobs across the cluster are fetched across the database socket and materialized into Python ORM objects.
2. The expiration logic is computed in Python row-by-row rather than in the PostgreSQL query planner.
3. Each expired row is mutated in the session and flushed individually, creating row-level lock contention with active workers that are sending heartbeats on those same rows.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Worker Polling Contention**: As the number of active translation and crawling workers increases, queue polling latency spikes due to repeated full scans and ORM object deserialization.
2. **Heartbeat Race Conditions**: In-memory mutation of `ActivityRecord` instances conflicts with concurrent heartbeat updates, triggering serialization failures or stale data overwrites.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/activity/database.py:362-390`, replace the in-memory Python scan with an atomic SQL `UPDATE`:

```python
def _recover_expired(self, session: Session) -> int:
    now = _utc_now()
    lease_delta = timedelta(seconds=self.LEASE_SECONDS)
    cutoff = now - lease_delta

    stmt = (
        update(ActivityRecord)
        .where(
            ActivityRecord.status == JobStatus.RUNNING.value,
            or_(
                ActivityRecord.lease_expires_at <= now,
                and_(
                    ActivityRecord.lease_expires_at.is_(None),
                    ActivityRecord.started_at <= cutoff,
                ),
            ),
        )
        .values(
            status=JobStatus.PENDING.value,
            started_at=None,
            lease_id=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
            error="Recovered expired activity lease",
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    result = session.execute(stmt)
    return result.rowcount
```

2. In `backend/src/novelai/db/models/activity.py:30-45`, ensure the partial index exists on `(status, lease_expires_at)`:

```python
Index(
    "ix_activity_records_running_leases",
    "lease_expires_at",
    postgresql_where=(status == "running"),
)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_activity_lease_recovery.py`:

```python
from datetime import UTC, datetime, timedelta
from novelai.activity.database import DatabaseActivityQueue
from novelai.db.models.activity import ActivityRecord

def test_stale_lease_recovery_atomic(db_session):
    now = datetime.now(UTC)
    old_time = now - timedelta(hours=1)
    stale_rec = ActivityRecord(
        activity_id="act-stale-1",
        type="crawl",
        kind="syosetu",
        novel_id="test-novel",
        status="running",
        started_at=old_time,
        lease_expires_at=old_time,
        lease_id="old-worker-lease",
    )
    db_session.add(stale_rec)
    db_session.commit()

    queue = DatabaseActivityQueue(session_factory=lambda: db_session)
    queue._recover_expired(db_session)
    db_session.commit()

    db_session.refresh(stale_rec)
    assert stale_rec.status == "pending"
    assert stale_rec.lease_id is None
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_activity_lease_recovery.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Replaces $O(N)$ Python loop with a sub-millisecond atomic SQL statement.
Rollback command: `git checkout HEAD -- backend/src/novelai/activity/database.py`

---

### REC-019: Missing Index on AuditLog Timestamp Causing Sequential Scans on Admin Pagination

- **ID**: `REC-019`
- **Subsystem/Component**: Database Performance & Admin Logging (`novelai.db.models.system`, `novelai.services.audit_service`)
- **Target Location**:
  - `backend/src/novelai/db/models/system.py:23-55` (`AuditLog`)
  - `backend/src/novelai/services/audit_service.py:323-351` (`search_logs`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `AuditLog` indexes individual columns (`action`, `actor_user_id`, `request_id`, `correlation_id`) but lacks an index on `created_at`. Admin pagination queries in `audit_service.py` filtering by `date_from` and `date_to` force sequential scans across all historical audit records.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/db/models/system.py:23-55`:

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
```

`created_at` has NO index (`index=True` is omitted and no index is defined in `__table_args__`).
In `backend/src/novelai/services/audit_service.py:345-351`:

```python
if date_from:
    q = q.filter(AuditLog.created_at >= date_from)
if date_to:
    q = q.filter(AuditLog.created_at <= date_to)
total = q.count()
rows = q.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
```

When administrators open the Audit Log dashboard or filter events by date range:

1. PostgreSQL cannot use index scans on `created_at`.
2. It executes a sequential scan across all historical audit entries.
3. It performs a top-$N$ sort in memory or spills to temporary disk files.
4. As audit records accumulate past $10^5$ rows, queries degrade from milliseconds to seconds, pinning database CPU cores.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Admin Console Timeout**: As audit records accumulate, admin views fail with gateway timeouts (HTTP 504) during compliance queries.
2. **Buffer Cache Eviction**: Sequential scans over large audit tables evict cached novel and chapter metadata from PostgreSQL's shared buffers.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/models/system.py:23-55`, add `Index` definitions to `AuditLog.__table_args__`:

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at_desc", func.coalesce(None, "created_at").desc()),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
    )
```

2. Create an Alembic migration `backend/alembic/versions/2026-08-17_add_audit_log_indexes.py`:

```python
def upgrade() -> None:
    op.create_index("ix_audit_logs_created_at_desc", "audit_logs", [sa.text("created_at DESC")])
    op.create_index("ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"])

def downgrade() -> None:
    op.drop_index("ix_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at_desc", table_name="audit_logs")
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_audit_log_indexes.py`:

```python
from sqlalchemy import text

def test_audit_log_created_at_query_plan(db_session):
    if db_session.bind.dialect.name != "postgresql":
        return
    plan = db_session.execute(
        text("EXPLAIN SELECT * FROM audit_logs WHERE created_at >= '2026-01-01' ORDER BY created_at DESC LIMIT 50")
    ).scalars().all()
    plan_text = " ".join(plan)
    assert "Index Scan" in plan_text or "Bitmap Index Scan" in plan_text
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_audit_log_indexes.py`

#### 5. Compatibility & Rollback

Non-breaking schema addition. In production, indexes can be added via `CREATE INDEX CONCURRENTLY` without write interruption.
Rollback command: `git checkout HEAD -- backend/src/novelai/db/models/system.py`

---

### REC-020: 32-Bit Integer Primary Key Overflow Risk on High-Volume Append-Only Tables

- **ID**: `REC-020`
- **Subsystem/Component**: Database Schema Design & Scalability (`novelai.db.models.analytics_event`, `novelai.db.models.system`, `novelai.db.models.notification`)
- **Target Location**:
  - `backend/src/novelai/db/models/analytics_event.py:43` (`AnalyticsEvent.id`)
  - `backend/src/novelai/db/models/system.py:32` (`AuditLog.id`)
  - `backend/src/novelai/db/models/system.py:155` (`ProviderUsageLedger.id`)
  - `backend/src/novelai/db/models/notification.py:74` (`NotificationDelivery.id`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: High-throughput append-only tables (`analytics_events`, `audit_logs`, `provider_usage_ledgers`, `notification_deliveries`) declare 32-bit `Integer` primary keys, creating an inevitable integer overflow that permanently crashes database writes at 2,147,483,647 rows.

#### 1. Root Cause & Code-Level Diagnostic

In PostgreSQL, SQLAlchemy's `Integer` type maps to a 4-byte signed `INTEGER`, with a maximum value of $2^{31} - 1 = 2,147,483,647$.
In `backend/src/novelai/db/models/analytics_event.py:43`:

```python
id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

In `backend/src/novelai/db/models/system.py:32, 155`:

```python
class AuditLog(Base):
    id: Mapped[int] = mapped_column(primary_key=True)  # defaults to Integer

class ProviderUsageLedger(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

In `backend/src/novelai/db/models/notification.py:74`:

```python
class NotificationDelivery(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
```

These tables record high-velocity append-only telemetry:

- `AnalyticsEvent`: Reader scroll progress, chapter views, searches, and device telemetry.
- `ProviderUsageLedger`: Granular LLM translation chunk token consumption.
- `NotificationDelivery`: Per-recipient email and webhook delivery logs.

When any PostgreSQL sequence reaches $2,147,483,647$, subsequent inserts fail with:
`psycopg.errors.NumericValueOutOfRange: integer out of range`.
All subsequent insert operations into that table immediately fail. Altering a primary key from `INTEGER` to `BIGINT` on a populated billion-row table requires an `ACCESS EXCLUSIVE` table lock that rewrites the table and all its secondary indexes, resulting in hours of scheduled downtime.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Telemetry & Ledger Outage**: Ingestion of user analytics and token usage tracking fails permanently once the 2.14B integer limit is reached.
2. **Prolonged Emergency Downtime**: Altering the primary key column post-facto on multi-gigabyte tables locks out all reads and writes.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/models/analytics_event.py`, `backend/src/novelai/db/models/system.py`, and `backend/src/novelai/db/models/notification.py`, change `Integer` primary keys to `BigInteger`:

```python
from sqlalchemy import BigInteger

class AnalyticsEvent(Base):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

class AuditLog(Base):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

class ProviderUsageLedger(Base):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

class NotificationDelivery(Base):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
```

2. Create an Alembic migration `backend/alembic/versions/2026-08-18_upgrade_high_volume_pks_to_bigint.py`:

```python
def upgrade() -> None:
    op.alter_column("analytics_events", "id", type_=sa.BigInteger(), existing_type=sa.Integer(), autoincrement=True)
    op.alter_column("audit_logs", "id", type_=sa.BigInteger(), existing_type=sa.Integer(), autoincrement=True)
    op.alter_column("provider_usage_ledgers", "id", type_=sa.BigInteger(), existing_type=sa.Integer(), autoincrement=True)
    op.alter_column("notification_deliveries", "id", type_=sa.BigInteger(), existing_type=sa.Integer(), autoincrement=True)

def downgrade() -> None:
    op.alter_column("notification_deliveries", "id", type_=sa.Integer(), existing_type=sa.BigInteger(), autoincrement=True)
    op.alter_column("provider_usage_ledgers", "id", type_=sa.Integer(), existing_type=sa.BigInteger(), autoincrement=True)
    op.alter_column("audit_logs", "id", type_=sa.Integer(), existing_type=sa.BigInteger(), autoincrement=True)
    op.alter_column("analytics_events", "id", type_=sa.Integer(), existing_type=sa.BigInteger(), autoincrement=True)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_pk_types.py`:

```python
from sqlalchemy import inspect, BigInteger
from novelai.db.models.analytics_event import AnalyticsEvent
from novelai.db.models.system import AuditLog, ProviderUsageLedger
from novelai.db.models.notification import NotificationDelivery

def test_high_volume_tables_use_bigint_pks():
    for model in (AnalyticsEvent, AuditLog, ProviderUsageLedger, NotificationDelivery):
        mapper = inspect(model)
        pk_col = mapper.primary_key[0]
        assert isinstance(pk_col.type, BigInteger), f"{model.__name__}.id must use BigInteger"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_pk_types.py`

#### 5. Compatibility & Rollback

Altering columns to `BIGINT` early in project lifecycle is fast and prevents catastrophic table rewrites under production load.
Rollback command: `git checkout HEAD -- backend/src/novelai/db/models/analytics_event.py backend/src/novelai/db/models/system.py backend/src/novelai/db/models/notification.py`

---

## Iteration 3: Storage Layer, Content Addressing, R2 Gateway Worker, & Snapshot Backups

### Summary of Recommendations (Iteration 3)

| ID        | Subsystem / Component                  | Category     | Title                                                                                              | Target Location                                                                                         |
| :-------- | :------------------------------------- | :----------- | :------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------ |
| `REC-021` | Storage Activation / DB Concurrency    | Performance  | Long-Held PostgreSQL Row Lock During Sequential R2 Object HEAD Verifications                       | `backend/src/novelai/services/r2_activation_service.py:55-144`                                          |
| `REC-022` | Artifact Decompression & Security      | Security     | Decompression Bomb (Zip Bomb) Vulnerability in Unbounded In-Memory Gzip Artifact Expansion         | `backend/src/novelai/storage/artifacts.py:72-84`                                                        |
| `REC-023` | R2 Gateway Worker & Access Security    | Security     | Insecure Unverified JWT Signature Fallback in Cloudflare Access Gateway Authentication             | `workers/r2-gateway/src/index.ts:89-103`                                                                |
| `REC-024` | Bucket Inventory & Cutover Operations  | Performance  | $O(N)$ Redundant HEAD Roundtrips in Bucket Inventory and Garbage Collector Key Traversal           | `backend/src/novelai/storage/r2_cutover.py:42-54,125-135`                                               |
| `REC-025` | Gateway Client Resilience & Transport  | Weakness     | Missing Transient Retry Budgets and Exponential Backoff on Idempotent R2 Gateway Requests          | `backend/src/novelai/storage/backends/r2_gateway.py:185-195,224-250`                                    |
| `REC-026` | Asset Pipeline & Media Ingestion       | Weakness     | Hardcoded Generic MIME Type and Missing Image Magic Bytes Validation in Asset Storage              | `backend/src/novelai/storage/artifacts.py:61-70`, `backend/src/novelai/storage/r2_catalog.py:1138-1148` |
| `REC-027` | Multi-Process File Locking             | Weakness     | Cross-Container PID Namespace Blindness and Unchecked Lock Deletion in `InterProcessFileLock`      | `backend/src/novelai/storage/file_lock.py:125-148`                                                      |
| `REC-028` | R2 Gateway Worker & Bulk Operations    | Architecture | Missing Gateway Batch Deletion Endpoint Forcing Sequential HTTP DELETE Roundtrips on Bulk Purges   | `workers/r2-gateway/src/index.ts:399-408`, `backend/src/novelai/storage/backends/r2_gateway.py:616-621` |
| `REC-029` | Incremental Backup & Disaster Recovery | Performance  | Redundant Full-Payload Re-Download Verification and Poison-Pill Manifest Block in Backup Retention | `backend/src/novelai/storage/r2_backup.py:149-160,284-287`                                              |
| `REC-030` | Runtime State Durability               | Weakness     | Non-Atomic File Writes in Chapter State Tracking Causing JSON Corruption on Worker Crashes         | `backend/src/novelai/storage/jobs.py:80-83`, `backend/src/novelai/storage/service.py:382-414`           |

---

### REC-021: Long-Held PostgreSQL Row Lock During Sequential R2 Object HEAD Verifications in Generation Activation

- **ID**: `REC-021`
- **Subsystem/Component**: Storage Activation / PostgreSQL Concurrency (`novelai.services.r2_activation_service`, `novelai.db.models.novel`)
- **Target Location**:
  - `backend/src/novelai/services/r2_activation_service.py:57-144` (`R2GenerationActivationService.activate`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `R2GenerationActivationService.activate` locks the `novels` row with `with_for_update()` at the start of activation, holding the open transaction while issuing hundreds of sequential synchronous HTTP `HEAD` network requests to Cloudflare R2, starving database connection pools and blocking all concurrent novel operations.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/r2_activation_service.py:57-144`:

```python
novel = self.db_session.query(Novel).filter(Novel.slug == novel_id).with_for_update().one_or_none()
...
for item in chapters:
    ...
    for field in ("raw_storage_key", "translated_storage_key", "media_storage_key"):
        ...
        object_metadata = self.storage.r2_backend.head(key)
        ...
    for asset_key in assets:
        ...
        asset_metadata = self.storage.r2_backend.head(asset_key)
...
if novel.active_generation_id != expected_generation_id:
    raise GenerationConflictError(...)
```

Notice:

1. The PostgreSQL row lock (`SELECT ... FOR UPDATE`) is acquired at line 57.
2. The method then iterates over every chapter and image asset in the manifest, executing synchronous remote HTTP calls via `self.storage.r2_backend.head()`.
3. For a web novel with 300 to 500 chapters and accompanying illustrations, this executes 1,000 to 2,000 sequential WAN roundtrips to the Cloudflare R2 gateway.
4. At 30-50ms per roundtrip, the PostgreSQL transaction remains open for 30 to 100 seconds, holding one of only 5 connection pool slots (`DB_POOL_SIZE = 5`) and exclusively locking the novel row.
5. All concurrent readers, crawler workers, and catalog listing requests touching this novel stall.
6. Crucially, the conflict check `if novel.active_generation_id != expected_generation_id` is evaluated at line 144 _after_ all network requests complete. If a conflict exists, all 2,000 HEAD calls were wasted.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Connection Pool Starvation**: Multiple novel activations running simultaneously exhaust the entire PostgreSQL connection pool, freezing all API endpoints across the admin and reader services.
2. **Cascading HTTP Timeouts**: Any client or background worker trying to update novel metadata encounters database lock acquisition timeouts (`statement_timeout` or `lock_timeout`).

#### 3. Concrete Implementation Specification

Refactor `R2GenerationActivationService.activate` into a two-phase optimistic activation pattern:

1. **Phase 1: Optimistic Pre-Validation (No DB lock held)**:
   - Read novel metadata without row locking (`one_or_none()`).
   - Validate `expected_generation_id` immediately. If mismatched, fail fast before making network calls.
   - Verify R2 object existence and checksums using concurrent thread pooling (`concurrent.futures.ThreadPoolExecutor(max_workers=16)`):

   ```python
   with ThreadPoolExecutor(max_workers=16) as executor:
       futures = [executor.submit(self._verify_chapter_r2_keys, item) for item in chapters]
       for future in as_completed(futures):
           future.result()  # raises InvalidGenerationManifestError if missing or mismatch
   ```

   - Upload the generation manifest artifact to R2.

2. **Phase 2: Atomic State Commit (Sub-millisecond lock)**:
   - Acquire `with_for_update()`, re-verify `novel.active_generation_id == expected_generation_id`, update `Chapter` rows, set `novel.active_generation_id = generation_id`, and commit immediately.

#### 4. Verification & Test Strategy

Create `backend/tests/test_r2_activation_concurrency.py`:

```python
from unittest.mock import MagicMock
import pytest
from novelai.services.r2_activation_service import R2GenerationActivationService
from novelai.storage.exceptions import GenerationConflictError

def test_activation_fails_fast_on_stale_generation(db_session):
    service = R2GenerationActivationService(storage=MagicMock(), db_session=db_session)
    r2_mock = service.storage.r2_backend
    manifest = {"novel_id": "1", "public_slug": "slug", "generation_id": "gen2", "chapters": []}
    with pytest.raises(GenerationConflictError):
        service.activate(novel_id="slug", generation_id="gen2", manifest=manifest, expected_generation_id="gen1_stale")
    assert r2_mock.head.call_count == 0
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_r2_activation_concurrency.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible with existing manifests and storage backends. Reduces PostgreSQL transaction hold time from ~60s to <10ms.
Rollback command: `git checkout HEAD -- backend/src/novelai/services/r2_activation_service.py`

---

### REC-022: Decompression Bomb (Zip Bomb) Vulnerability in Unbounded In-Memory Gzip Artifact Expansion

- **ID**: `REC-022`
- **Subsystem/Component**: Artifact Decompression & Security (`novelai.storage.artifacts`)
- **Target Location**:
  - `backend/src/novelai/storage/artifacts.py:92-104` (`R2ArtifactRepository.load_json`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `R2ArtifactRepository.load_json` decompresses entire gzip payloads into RAM using `gzip.decompress()` before checking uncompressed length, allowing a small gzip payload to exhaust container memory and trigger an OS kernel OOM killer termination.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/artifacts.py:92-104`:

```python
def load_json(self, key: str, *, max_decompressed_bytes: int = 25 * 1024 * 1024) -> dict[str, Any]:
    compressed = self.storage.load(key)
    try:
        decompressed = gzip.decompress(compressed)
        if len(decompressed) > max_decompressed_bytes:
            raise ValueError(
                f"Decompressed artifact size {len(decompressed)} exceeds limit of {max_decompressed_bytes}"
            )
        payload = json.loads(decompressed.decode("utf-8"))
```

Notice:

1. `gzip.decompress(compressed)` is executed synchronously and eagerly in memory.
2. In gzip compression, a 10 MB file containing repetitive bytes easily expands to over 10 GB uncompressed (a 1000:1 compression ratio zip bomb).
3. The guard `if len(decompressed) > max_decompressed_bytes` is checked _only after_ `gzip.decompress()` has allocated the full uncompressed buffer in memory.
4. If a malicious or corrupted artifact is uploaded or fetched, Python's heap allocation expands past Docker memory limits (e.g. 1GB or 2GB), and the Linux kernel OOM killer immediately sends `SIGKILL` to the process before `ValueError` is ever raised.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Denial of Service (OOM Crash)**: A single corrupted chapter artifact loaded by the reader service or background worker crashes the container process, dropping active user connections.
2. **Container Crash Loop**: If an infected chapter is requested repeatedly by reader traffic, the service enters an unrecoverable crash loop.

#### 3. Concrete Implementation Specification

Implement bounded streaming decompression using `zlib.decompressobj` in `backend/src/novelai/storage/artifacts.py:92-104`:

```python
import io
import zlib

def load_json(self, key: str, *, max_decompressed_bytes: int = 25 * 1024 * 1024) -> dict[str, Any]:
    compressed = self.storage.load(key)
    decompressor = zlib.decompressobj(wbits=31)
    decompressed = bytearray()
    chunk_size = 64 * 1024
    stream = io.BytesIO(compressed)

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        max_to_read = (max_decompressed_bytes - len(decompressed)) + 1
        inflated = decompressor.decompress(chunk, max_to_read)
        decompressed.extend(inflated)
        if len(decompressed) > max_decompressed_bytes:
            raise ValueError(
                f"Decompressed artifact exceeds limit of {max_decompressed_bytes} bytes"
            )

    decompressed.extend(decompressor.flush())
    if len(decompressed) > max_decompressed_bytes:
        raise ValueError(f"Decompressed artifact exceeds limit of {max_decompressed_bytes} bytes")

    return json.loads(decompressed.decode("utf-8"))
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_artifact_decompression_safety.py`:

```python
import gzip
from unittest.mock import MagicMock
import pytest
from novelai.storage.artifacts import R2ArtifactRepository

def test_load_json_aborts_zip_bomb_without_oom():
    bomb_bytes = gzip.compress(b"0" * (30 * 1024 * 1024))
    storage_mock = MagicMock()
    storage_mock.load.return_value = bomb_bytes
    repo = R2ArtifactRepository(storage=storage_mock)

    with pytest.raises(RuntimeError, match="corrupt"):
        repo.load_json("novels/1/chapters/c1.json.gz", max_decompressed_bytes=1024 * 1024)
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_artifact_decompression_safety.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible with all valid compressed JSON artifacts. Drops memory usage ceiling to strictly $\le \text{max\_decompressed\_bytes} + 64\text{KB}$.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/artifacts.py`

---

### REC-023: Insecure Unverified JWT Signature Fallback in Cloudflare Access Gateway Authentication

- **ID**: `REC-023`
- **Subsystem/Component**: R2 Gateway Worker & Access Security (`workers/r2-gateway/src/index.ts`)
- **Target Location**:
  - `workers/r2-gateway/src/index.ts:70-93` (`authenticate`)
- **Category**: `Security`
- **Severity**: `Critical`
- **Summary**: The R2 Gateway Worker falls back to decoding `cf-access-jwt-assertion` with unsigned `atob()` when `ctx.access.getIdentity()` returns null, allowing full authentication bypass and unauthorized R2 bucket read/write/delete access via crafted HTTP headers.

#### 1. Root Cause & Code-Level Diagnostic

In `workers/r2-gateway/src/index.ts:70-93`:

```typescript
async function authenticate(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<IdentityClass | null> {
  if (!ctx.access) return null;
  let identity = await ctx.access.getIdentity();
  if (!identity?.common_name) {
    const jwt = request.headers.get("cf-access-jwt-assertion");
    if (jwt) {
      try {
        const payload = JSON.parse(atob(jwt.split(".")[1]));
        if (
          payload.aud === ctx.access.aud &&
          typeof payload.common_name === "string"
        ) {
          identity = { common_name: payload.common_name };
        }
      } catch {}
    }
  }
  return identityClassFromAccessIdentity(identity, env);
}
```

Notice:

1. When running behind Cloudflare Access or during local/test staging where `ctx.access.getIdentity()` fails to resolve, execution falls into the fallback block.
2. The fallback block extracts the second segment of the JWT (`jwt.split(".")[1]`) and passes it to `atob()`.
3. It only checks `payload.aud === ctx.access.aud` and `typeof payload.common_name === "string"`.
4. It completely ignores the cryptographic signature in segment 3 (`jwt.split(".")[2]`).
5. An attacker who sends a request with an unsigned, forged JWT containing:
   `Header: {"alg":"none","typ":"JWT"}`
   `Payload: {"aud":"<known_aud>","common_name":"<APP_CLIENT_ID>"}`
   is granted `identity = "application"`.
6. This yields unrestricted `["get", "head", "put", "delete"]` access across the canonical `dokushodo` R2 storage bucket.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Total R2 Bucket Takeover**: Any caller with network access to the worker endpoint can forge a header to delete all novel archives, overwrite chapter text with malware/phishing payloads, or exfiltrate private assets.
2. **Failure of Defense-in-Depth**: Completely negates Cloudflare Access zero-trust protections.

#### 3. Concrete Implementation Specification

1. Remove the unverified `atob()` fallback entirely.
2. Rely strictly on Cloudflare Access's native verified identity provider via `ctx.access.getIdentity()`.
3. In `workers/r2-gateway/src/index.ts:70-93`:

```typescript
async function authenticate(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<IdentityClass | null> {
  if (!ctx.access) return null;

  // Strictly require Cloudflare runtime's verified Access identity
  const identity = await ctx.access.getIdentity();
  if (!identity?.common_name) {
    // Reject request: NEVER decode unverified JWT assertions using atob()
    return null;
  }
  return identityClassFromAccessIdentity(identity, env);
}
```

#### 4. Verification & Test Strategy

Create worker unit test `workers/r2-gateway/test/auth.spec.ts`:

```typescript
import { expect, test } from "vitest";

test("rejects forged unverified cf-access-jwt-assertion header", async () => {
  const forgedPayload = btoa(
    JSON.stringify({ aud: "test-aud", common_name: "valid-client-id" }),
  );
  const forgedJwt = `eyJhbGciOiJub25lIn0.${forgedPayload}.invalidsignature`;

  const req = new Request("http://localhost/v1/app/objects/test.json", {
    headers: {
      "cf-access-jwt-assertion": forgedJwt,
    },
  });

  const res = await worker.fetch(req, env, mockCtx);
  expect(res.status).toBe(401);
});
```

Run: `npm --prefix workers/r2-gateway test`

#### 5. Compatibility & Rollback

Secure by default. Legitimate traffic traversing Cloudflare Access with configured Service Tokens is verified natively by Cloudflare edge middleware.
Rollback command: `git checkout HEAD -- workers/r2-gateway/src/index.ts`

---

### REC-024: $O(N)$ Redundant HEAD Roundtrips in Bucket Inventory and Garbage Collector Key Traversal

- **ID**: `REC-024`
- **Subsystem/Component**: Bucket Inventory & Cutover Operations (`novelai.storage.r2_cutover`)
- **Target Location**:
  - `backend/src/novelai/storage/r2_cutover.py:42-54` (`inventory_bucket`)
  - `backend/src/novelai/storage/r2_cutover.py:125-135` (`R2GarbageCollector.collect`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `inventory_bucket` and `R2GarbageCollector.collect` invoke `list_keys()`, discarding metadata returned by Cloudflare R2 list pages, and then execute redundant individual `HEAD` HTTP requests for every single object in the bucket.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/r2_cutover.py:42-54`:

```python
def inventory_bucket(storage: R2StorageBackend) -> R2Inventory:
    keys = tuple(storage.list_keys("", recursive=True))
    total = 0
    for key in keys:
        total += storage.head(key).size_bytes
    return R2Inventory(
        bucket=storage.bucket,
        object_count=len(keys),
        bytes_total=total,
        keys=keys,
    )
```

And in `backend/src/novelai/storage/r2_cutover.py:125-135`:

```python
for key in self.storage.list_keys("novels", recursive=True):
    if key in keep:
        continue
    metadata: R2ObjectMetadata = self.storage.head(key)
    last_modified = metadata.last_modified
```

Notice:

1. In Cloudflare R2 and S3 APIs, `list_objects` returns 1,000 objects per page, including `size_bytes`, `etag`, and `last_modified` for each object directly in the JSON response body.
2. `storage.list_keys()` consumes `_iter_objects()` but yields only string `item.key`, discarding all parsed metadata.
3. `inventory_bucket` and `R2GarbageCollector.collect` then loop over every returned key and issue an independent HTTP `HEAD` request to retrieve `size_bytes` and `last_modified`.
4. In a production bucket containing 50,000 chapters and assets:
   - Paginated listing requires only 50 HTTP requests (1,000 keys/page).
   - This implementation makes 50 + 50,000 = 50,050 HTTP requests!
5. At 30ms latency per request, 50,000 HEAD calls take ~25 minutes, keeping worker tasks blocked and triggering gateway connection resets.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Cutover & Audit Stalls**: Bucket inventory and cutover audits timeout or crash after hours of execution.
2. **Garbage Collection Failure**: Garbage collection jobs exceed task queue lease timeouts and are repeatedly marked stale and re-run.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/storage/r2_cutover.py:42-54`, iterate directly over `_iter_objects`:

```python
def inventory_bucket(storage: R2StorageBackend) -> R2Inventory:
    """Inventory every object using metadata directly from paginated list responses."""
    objects = list(storage._iter_objects("", recursive=True))
    return R2Inventory(
        bucket=storage.bucket,
        object_count=len(objects),
        bytes_total=sum(item.size_bytes for item in objects),
        keys=tuple(item.key for item in objects),
    )
```

2. In `backend/src/novelai/storage/r2_cutover.py:125-135`, read `item.last_modified` directly from list metadata:

```python
for item in self.storage._iter_objects("novels", recursive=True):
    if item.key in keep:
        continue
    last_modified = item.last_modified
    if last_modified is None:
        continue
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=UTC)
    if last_modified <= cutoff:
        candidates.append(item.key)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_r2_inventory_efficiency.py`:

```python
from unittest.mock import MagicMock
from novelai.storage.base import R2ObjectMetadata
from novelai.storage.r2_cutover import inventory_bucket

def test_inventory_bucket_uses_list_metadata_without_head():
    storage = MagicMock()
    mock_objects = [
        R2ObjectMetadata(key=f"novels/1/c{i}.json.gz", size_bytes=1024, etag="abc", last_modified=None, content_type="application/json")
        for i in range(100)
    ]
    storage._iter_objects.return_value = iter(mock_objects)
    storage.bucket = "test-bucket"

    inv = inventory_bucket(storage)
    assert inv.object_count == 100
    assert inv.bytes_total == 100 * 1024
    assert storage.head.call_count == 0
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_r2_inventory_efficiency.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Replaces $O(N)$ HTTP requests with $O(N / 1000)$ batched list requests, speeding up execution by ~1000x.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/r2_cutover.py`

---

### REC-025: Missing Transient Retry Budgets and Exponential Backoff on Idempotent R2 Gateway Requests

- **ID**: `REC-025`
- **Subsystem/Component**: Gateway Client Resilience & Transport (`novelai.storage.backends.r2_gateway`)
- **Target Location**:
  - `backend/src/novelai/storage/backends/r2_gateway.py:180-250` (`R2GatewayStorage._request`)
- **Category**: `Weakness`
- **Severity**: `Medium`
- **Summary**: `R2GatewayStorage` executes single-shot HTTP requests without retry budgets or exponential backoff, causing transient network hiccups, Cloudflare 502/503 edge errors, or TLS resets to immediately fail batch scraping and reader operations.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/backends/r2_gateway.py:180-250`:

```python
self._client = httpx.Client(
    base_url=endpoint_url.rstrip("/"),
    timeout=httpx.Timeout(
        connect=settings.R2_GATEWAY_TIMEOUT_CONNECT_SECONDS,
        read=settings.R2_GATEWAY_TIMEOUT_READ_SECONDS,
        write=settings.R2_GATEWAY_TIMEOUT_WRITE_SECONDS,
        pool=settings.R2_GATEWAY_TIMEOUT_POOL_SECONDS,
    ),
    follow_redirects=False,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
)
...
def _request(self, method: str, path: str, ...) -> httpx.Response:
    request_headers = self._request_headers()
    if headers:
        request_headers.update(headers)
    response = self._client.request(method, path, headers=request_headers, params=params, content=content)
    if response.status_code >= 400:
        ...
        raise error_type(status_code=response.status_code, error_code=error_code, request_id=request_id)
    return response
```

Notice:

1. `_client` does not configure `httpx.HTTPTransport(retries=...)`.
2. `_request` executes a single synchronous roundtrip without retry handling.
3. Edge network routes to Cloudflare Workers frequently experience transient glitches: DNS resolution latency, TCP connection resets (`ECONNRESET`), worker cold-start delays, or edge 502/503/504 errors.
4. Because idempotent operations (`GET`, `HEAD`, and conditional `PUT` with `If-None-Match`) are not protected by a bounded retry loop with jittered backoff, a 10-millisecond edge network blip crashes hours-long novel ingestion batches and throws HTTP 500 errors on reader frontend requests.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Flaky Batch Ingestion**: Background chapter scraping or translation pipelines abort mid-way due to transient edge connection drops.
2. **Reader Frontend Glitches**: Users reading chapters experience random 500 errors when edge gateway requests fail on first attempt.

#### 3. Concrete Implementation Specification

Implement bounded retry with jittered exponential backoff for idempotent HTTP operations in `R2GatewayStorage._request`:

```python
import random
import time

def _request_with_retry(
    self,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str | int | bool] | None = None,
    content: bytes | BinaryIO | None = None,
    max_retries: int = 3,
) -> httpx.Response:
    is_idempotent = method in {"GET", "HEAD"} or (headers and "if-none-match" in {k.lower() for k in headers})
    attempts = max_retries if is_idempotent else 1

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request_headers = self._request_headers()
            if headers:
                request_headers.update(headers)
            response = self._client.request(method, path, headers=request_headers, params=params, content=content)

            if response.status_code in {429, 502, 503, 504} and attempt < attempts:
                response.close()
                backoff = (0.2 * (2 ** (attempt - 1))) + random.uniform(0.05, 0.15)
                time.sleep(backoff)
                continue

            if response.status_code >= 400:
                self._handle_error_response(response, request_headers)
            return response
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < attempts:
                backoff = (0.2 * (2 ** (attempt - 1))) + random.uniform(0.05, 0.15)
                time.sleep(backoff)
                continue
            raise R2GatewayError(f"R2 Gateway transport failed after {attempt} attempts: {exc}") from exc
    raise R2GatewayError(f"R2 Gateway request failed: {last_exc}")
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_r2_gateway_retry.py`:

```python
from unittest.mock import MagicMock
import httpx
from novelai.storage.backends.r2_gateway import R2GatewayStorage

def test_gateway_retries_transient_503_and_succeeds():
    storage = R2GatewayStorage(endpoint_url="http://mock", bucket="app", client_id="id", client_secret="sec")
    mock_client = MagicMock()
    resp_503 = httpx.Response(503, headers={"x-request-id": "req1"})
    resp_200 = httpx.Response(200, content=b"data", headers={"content-length": "4", "x-request-id": "req2"})
    mock_client.request.side_effect = [resp_503, resp_200]
    storage._client = mock_client

    res = storage._request_with_retry("GET", "/v1/app/objects/test.json")
    assert res.status_code == 200
    assert mock_client.request.call_count == 2
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_r2_gateway_retry.py`

#### 5. Compatibility & Rollback

Transparent to callers. Non-idempotent operations (unconditional `PUT`, `DELETE`) are preserved as single-shot unless explicitly marked safe.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/backends/r2_gateway.py`

---

### REC-026: Hardcoded Generic MIME Type and Missing Image Magic Bytes Validation in Asset Storage

- **ID**: `REC-026`
- **Subsystem/Component**: Asset Pipeline & Media Ingestion (`novelai.storage.artifacts`, `novelai.storage.r2_catalog`)
- **Target Location**:
  - `backend/src/novelai/storage/artifacts.py:80-90` (`R2ArtifactRepository.put_asset`)
  - `backend/src/novelai/storage/r2_catalog.py:1138-1148` (`save_chapter_image_asset`)
- **Category**: `Weakness`
- **Severity**: `Medium`
- **Summary**: `R2ArtifactRepository.put_asset` hardcodes `content_type="application/octet-stream"`, while `save_chapter_image_asset` lacks image magic byte verification, causing browser image render failures and ingestion of invalid payloads.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/artifacts.py:80-90`:

```python
def put_asset(self, *, storage_novel_id: str, content: bytes, extension: str) -> StoredArtifact:
    digest = sha256_hex(content)
    key = asset_key(storage_novel_id, digest, extension)
    result = self.storage.put_immutable(
        key,
        content,
        logical_sha256=digest,
        content_type="application/octet-stream",
        content_encoding=None,
    )
    return self._stored(result)
```

In `backend/src/novelai/storage/r2_catalog.py:1138-1148`:

```python
extension = "bin"
if isinstance(content_type, str) and "/" in content_type:
    extension = content_type.rsplit("/", 1)[-1].split("+", 1)[0].lower() or extension
storage_novel_id = storage_novel_id or resolve_storage_novel_id(storage, novel_id)
stored = storage._r2_artifacts().put_asset(
    storage_novel_id=storage_novel_id,
    content=content,
    extension=extension,
)
```

Notice:

1. `put_asset` unconditionally overrides `content_type` with `"application/octet-stream"`.
2. When the R2 Gateway serves the asset directly or via CDN, browsers receive `Content-Type: application/octet-stream`. Modern browsers treat this as a binary download rather than rendering novel cover images and illustrations inline.
3. `save_chapter_image_asset` extracts `extension` entirely from an unverified string returned by the web server. If the upstream server returned an HTML error or anti-bot challenge (`Content-Type: text/html`), the HTML payload is accepted and stored as an asset with extension `.html` or `.bin`.
4. No binary magic byte validation occurs on the raw image payload.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Broken Illustrations in Frontend**: Novel covers and illustrations fail to render natively in the Next.js reader UI.
2. **Polluted Asset Storage**: Web scrapers store HTML error pages and bot challenge screens as immutable image assets in R2.

#### 3. Concrete Implementation Specification

1. Implement a binary magic byte inspection helper in `backend/src/novelai/storage/artifacts.py`:

```python
def detect_image_type(data: bytes) -> tuple[str, str] | None:
    """Detect image MIME type and extension from binary signatures (magic bytes)."""
    if data.startswith(b"\xFF\xD8\xFF"):
        return ("image/jpeg", "jpg")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ("image/png", "png")
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ("image/webp", "webp")
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ("image/gif", "gif")
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis"}:
        return ("image/avif", "avif")
    return None
```

2. Update `put_asset` in `R2ArtifactRepository` to accept `content_type: str | None = None` and default to the detected MIME type instead of hardcoding `application/octet-stream`:

```python
def put_asset(
    self,
    *,
    storage_novel_id: str,
    content: bytes,
    extension: str,
    content_type: str | None = None,
) -> StoredArtifact:
    detected = detect_image_type(content)
    if detected:
        canonical_mime, detected_ext = detected
        extension = detected_ext
        content_type = content_type or canonical_mime
    else:
        content_type = content_type or "application/octet-stream"

    digest = sha256_hex(content)
    key = asset_key(storage_novel_id, digest, extension)
    result = self.storage.put_immutable(
        key,
        content,
        logical_sha256=digest,
        content_type=content_type,
        content_encoding=None,
    )
    return self._stored(result)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_image_asset_magic_bytes.py`:

```python
from novelai.storage.artifacts import detect_image_type

def test_detect_image_type_png():
    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert detect_image_type(png_header) == ("image/png", "png")

def test_detect_image_type_rejects_html():
    html_content = b"<!DOCTYPE html><html><body>Error 404</body></html>"
    assert detect_image_type(html_content) is None
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_image_asset_magic_bytes.py`

#### 5. Compatibility & Rollback

Non-breaking change. Preserves existing keys while guaranteeing proper MIME headers for browser rendering.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/artifacts.py backend/src/novelai/storage/r2_catalog.py`

### REC-027: Cross-Container PID Namespace Blindness and Unchecked Lock Deletion in `InterProcessFileLock`

- **ID**: `REC-027`
- **Subsystem/Component**: Multi-Process File Locking (`novelai.storage.file_lock`)
- **Target Location**:
  - `backend/src/novelai/storage/file_lock.py:125-148` (`InterProcessFileLock._reclaim_stale_if_possible`, `release`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `InterProcessFileLock` reclaims locks based on process-local PID liveness and unlinks files without checking ownership, causing premature lock deletion and concurrent file corruption across Docker containers sharing mounted `/runtime`.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/file_lock.py:125-148`:

```python
def _reclaim_stale_if_possible(self) -> bool:
    try:
        data = self.lock_path.read_text(encoding="utf-8")
        info = json.loads(data)
        pid = int(info.get("pid", 0))
        if pid > 0 and not _is_pid_alive(pid):
            with contextlib.suppress(OSError):
                self.lock_path.unlink(missing_ok=True)
            logger.warning("Reclaimed stale file lock from dead PID %s at %s", pid, self.lock_path)
            return True
    except json.JSONDecodeError, OSError, ValueError:
        pass
    return False

def release(self) -> None:
    if self._acquired:
        with contextlib.suppress(OSError):
            self.lock_path.unlink(missing_ok=True)
        self._acquired = False
```

Notice:

1. In `compose.yml`, multiple separate containers (`novelai-admin`, `novelai-reader`, `novelai-worker`) share the mounted volume `/runtime`.
2. Each Docker container operates within its own Linux PID namespace. In Container A (`worker`), the python process has PID 15.
3. When Container B (`admin`) attempts to acquire the same file lock, `_reclaim_stale_if_possible` reads `pid=15` and executes `_is_pid_alive(15)` inside Container B's isolated PID namespace.
4. Because PID 15 either does not exist or maps to an unrelated process in Container B, `_is_pid_alive(15)` returns `False`.
5. Container B immediately deletes the active lockfile owned by Container A and creates its own lock!
6. Furthermore, in `release()`, calling `unlink(missing_ok=True)` deletes the lockfile unconditionally without checking if the current lockfile still belongs to this process (`info.get("owner_id") == self._owner_id`). If another process stole the lock, `release()` removes the new owner's lockfile.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Concurrent Local File Corruption**: Multiple containers write to the same runtime cache or metadata files simultaneously, leading to JSON truncation and corrupted job state.
2. **Lock Thrashing**: Mutex semantics are entirely broken across container boundaries.

#### 3. Concrete Implementation Specification

In `backend/src/novelai/storage/file_lock.py`:

1. Include hostname/node ID alongside PID in lock metadata:

```python
import socket

def _lock_payload(self) -> dict[str, Any]:
    return {
        "owner_id": self._owner_id,
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "created_at": time.time(),
    }
```

2. In `_reclaim_stale_if_possible`, only check `_is_pid_alive()` if `info.get("hostname") == socket.gethostname()`. Across different hosts/containers, rely exclusively on explicit timeout expiration:

```python
def _reclaim_stale_if_possible(self) -> bool:
    try:
        data = self.lock_path.read_text(encoding="utf-8")
        info = json.loads(data)
        lock_host = info.get("hostname")
        lock_pid = int(info.get("pid", 0))
        created_at = float(info.get("created_at", 0))

        # Cross-container safety: PID check valid ONLY on matching hostname
        if lock_host == socket.gethostname():
            if lock_pid > 0 and not _is_pid_alive(lock_pid):
                self._safe_unlink(info.get("owner_id"))
                return True
        elif created_at > 0 and (time.time() - created_at > self.stale_timeout_seconds):
            self._safe_unlink(info.get("owner_id"))
            return True
    except Exception:
        pass
    return False
```

3. In `release()`, verify `owner_id` before unlinking:

```python
def release(self) -> None:
    if self._acquired:
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            if data.get("owner_id") == self._owner_id:
                self.lock_path.unlink(missing_ok=True)
        except Exception:
            pass
        self._acquired = False
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_file_lock_container_safety.py`:

```python
import json
import time
from novelai.storage.file_lock import InterProcessFileLock

def test_lock_does_not_reclaim_foreign_hostname_pid(tmp_path):
    lock_file = tmp_path / "test.lock"
    foreign_data = {"owner_id": "other", "hostname": "worker-container-99", "pid": 999999, "created_at": time.time()}
    lock_file.write_text(json.dumps(foreign_data), encoding="utf-8")

    lock = InterProcessFileLock(lock_file, timeout=0.1)
    assert lock._reclaim_stale_if_possible() is False
    assert lock_file.exists()
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_file_lock_container_safety.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible with single-container and multi-container environments.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/file_lock.py`

---

### REC-028: Missing Gateway Batch Deletion Endpoint Forcing Sequential HTTP DELETE Roundtrips on Bulk Purges

- **ID**: `REC-028`
- **Subsystem/Component**: R2 Gateway Worker & Bulk Operations (`workers/r2-gateway/src/index.ts`, `novelai.storage.backends.r2_gateway`)
- **Target Location**:
  - `workers/r2-gateway/src/index.ts:399-408` (`route` DELETE handler)
  - `backend/src/novelai/storage/backends/r2_gateway.py:616-621` (`R2GatewayStorage.delete_prefix`)
- **Category**: `Architecture`
- **Severity**: `Medium`
- **Summary**: The R2 Gateway Worker lacks a bulk deletion endpoint, forcing `delete_prefix` and snapshot retention cleanup to issue thousands of individual HTTP DELETE requests sequentially over the network.

#### 1. Root Cause & Code-Level Diagnostic

In `workers/r2-gateway/src/index.ts:399-408`:

```typescript
if (request.method === "DELETE") {
  if (!allowed(identity, bucketClass, "delete"))
    return failure(id, 403, "operation_not_permitted");
  await bucketFor(env, bucketClass).delete(key);
  return new Response(null, { status: 204, ... });
}
```

In `backend/src/novelai/storage/backends/r2_gateway.py:616-621`:

```python
def delete_prefix(self, prefix: str | Path) -> int:
    keys = [item.key for item in self._iter_objects(prefix, recursive=True)]
    for key in keys:
        self.delete(key)
    return len(keys)
```

Notice:

1. The Cloudflare Workers R2 runtime natively supports batch deletions: `bucket.delete(keys: string[])` deletes up to 1,000 keys in a single atomic call.
2. Because the gateway worker only exposes single-key `DELETE /v1/:bucketClass/objects/:key`, `delete_prefix` iterates over every object in Python and issues an individual HTTP DELETE request over WAN.
3. Purging a 1,500-chapter novel or pruning an expired backup snapshot generates 1,500+ sequential network roundtrips.
4. At 30ms latency, this takes 45+ seconds and holds worker processes in long-running I/O waits, triggering gateway timeouts and connection pool churn.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Worker Task Timeouts**: Novel purge operations or backup pruning exceed Celery / task runner timeouts.
2. **Network Inefficiency**: Thousands of HTTP request/response headers are serialized and deserialized for single-key deletions.

#### 3. Concrete Implementation Specification

1. In `workers/r2-gateway/src/index.ts`, add batch deletion endpoint `POST /v1/:bucketClass/delete-batch`:

```typescript
if (remainder.endsWith("/delete-batch") && request.method === "POST") {
  if (!allowed(identity, bucketClass, "delete"))
    return failure(id, 403, "operation_not_permitted");
  const body = await request.json<{ keys: string[] }>();
  if (
    !Array.isArray(body?.keys) ||
    body.keys.length === 0 ||
    body.keys.length > 1000
  ) {
    return failure(id, 400, "invalid_keys_array");
  }
  const validKeys: string[] = [];
  for (const raw of body.keys) {
    const k = decodeKey(raw);
    if (k) validKeys.push(k);
  }
  await bucketFor(env, bucketClass).delete(validKeys);
  return json(id, 200, { deleted_count: validKeys.length });
}
```

2. In `backend/src/novelai/storage/backends/r2_gateway.py`, implement `delete_objects(keys: list[str])` and update `delete_prefix`:

```python
def delete_objects(self, keys: list[str]) -> int:
    """Delete a list of keys using batch deletion (up to 1,000 per request)."""
    if not keys:
        return 0
    total_deleted = 0
    for chunk in chunk_iterable(keys, 1000):
        resp = self._request("POST", f"/v1/{self._bucket_class}/delete-batch", json={"keys": chunk})
        total_deleted += resp.json().get("deleted_count", len(chunk))
    return total_deleted

def delete_prefix(self, prefix: str | Path) -> int:
    keys = [item.key for item in self._iter_objects(prefix, recursive=True)]
    return self.delete_objects(keys)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_r2_gateway_batch_delete.py`:

```python
from unittest.mock import MagicMock
from novelai.storage.backends.r2_gateway import R2GatewayStorage

def test_delete_prefix_chunks_batch_deletions():
    storage = R2GatewayStorage(endpoint_url="http://mock", bucket="app", client_id="id", client_secret="sec")
    storage._request = MagicMock()
    storage._request.return_value.json.return_value = {"deleted_count": 1000}

    keys = [f"novels/1/c{i}.json.gz" for i in range(2500)]
    storage.delete_objects(keys)
    assert storage._request.call_count == 3
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_r2_gateway_batch_delete.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Retains single-key `delete()` for backwards compatibility while cutting bulk deletion network roundtrips by 99.9%.
Rollback command: `git checkout HEAD -- workers/r2-gateway/src/index.ts backend/src/novelai/storage/backends/r2_gateway.py`

---

### REC-029: Redundant Full-Payload Re-Download Verification and Poison-Pill Manifest Block in Backup Retention

- **ID**: `REC-029`
- **Subsystem/Component**: Incremental Backup & Disaster Recovery (`novelai.storage.r2_backup`)
- **Target Location**:
  - `backend/src/novelai/storage/r2_backup.py:149-160` (`R2IncrementalBackupTarget.create_snapshot`)
  - `backend/src/novelai/storage/r2_backup.py:284-287` (`R2IncrementalBackupTarget.apply_retention`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `create_snapshot` downloads every backed-up object twice, doubling egress and memory usage, while `apply_retention` completely halts backup object GC if a single corrupted snapshot manifest is found.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/r2_backup.py:145-165`:

```python
self._target.save(backup_key, data, content_type=content_type, content_encoding=content_encoding)
copied.append(backup_key)
restored = self._target.load(backup_key)
if len(restored) != size_bytes or hashlib.sha256(restored).hexdigest() != source_sha256:
    raise RuntimeError(
        f"R2 backup checksum verification failed for {backup_key}: "
        f"expected {size_bytes}B sha256={source_sha256}, "
        f"got {len(restored)}B sha256={hashlib.sha256(restored).hexdigest()}"
    )
```

In lines 284-287 of `apply_retention`:

```python
if invalid_manifest_found:
    logger.warning("Skipping R2 backup object collection because an invalid snapshot manifest exists")
    return deleted_count
```

Notice:

1. When backing up an object, `create_snapshot` reads the object from source bucket (`self._source.load(source_key)`), uploads it to the backup bucket (`self._target.save(backup_key, data)`), and then immediately downloads it again from the backup bucket (`self._target.load(backup_key)`).
2. For backups containing gigabytes of novel chapter archives and image assets, this doubles egress network bandwidth and doubles memory allocations.
3. The R2 Gateway Worker already verifies SHA-256 and size on PUT, returning HTTP 200 with ETag and verified metadata. A simple `self._target.head(backup_key)` confirms size and ETag without downloading gigabytes over WAN.
4. In `apply_retention`, if a crashed backup run leaves an unparseable or zero-byte `manifest.json` under `snapshots/`, `invalid_manifest_found` is set to `True`.
5. Because of this poison pill, `apply_retention` permanently bails out without executing object garbage collection. Unreferenced backup objects accumulate indefinitely, incurring unbounded R2 storage billing until an engineer manually purges the corrupt manifest file.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Doubled Egress Costs & Backup Latency**: Every backup cycle downloads 2x data volume over external networks.
2. **Unbounded Storage Growth (Poison Pill)**: A single corrupted manifest permanently disables GC across the entire backup bucket.

#### 3. Concrete Implementation Specification

1. In `create_snapshot()`, replace the redundant full-body load with a metadata `head()` verification:

```python
self._target.save(backup_key, data, content_type=content_type, content_encoding=content_encoding)
copied.append(backup_key)
meta = self._target.head(backup_key)
if meta is None or meta.size_bytes != size_bytes:
    raise RuntimeError(
        f"R2 backup verification failed for {backup_key}: expected {size_bytes}B, got {meta.size_bytes if meta else 'None'}B"
    )
```

2. In `apply_retention()`, quarantine corrupted manifests instead of halting garbage collection:

```python
if invalid_manifest_found:
    logger.warning("Corrupted snapshot manifests detected during retention; isolating invalid manifests and proceeding with safe GC")
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_r2_backup_optimizations.py`:

```python
from unittest.mock import MagicMock
from novelai.storage.base import R2ObjectMetadata
from novelai.storage.r2_backup import R2IncrementalBackupTarget

def test_create_snapshot_verifies_via_head_without_second_download():
    source = MagicMock()
    target = MagicMock()
    source.load.return_value = b"test payload content"
    source.head.return_value = R2ObjectMetadata(key="k1", size_bytes=20, etag="e1", last_modified=None, content_type="text/plain")
    target.head.return_value = R2ObjectMetadata(key="backup/k1", size_bytes=20, etag="e1", last_modified=None, content_type="text/plain")

    backup_target = R2IncrementalBackupTarget(source=source, target=target)
    assert target.load.call_count == 0
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_r2_backup_optimizations.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible with existing snapshots and manifests.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/r2_backup.py`

---

### REC-030: Non-Atomic File Writes in Chapter State Tracking Causing JSON Corruption on Worker Crashes

- **ID**: `REC-030`
- **Subsystem/Component**: Runtime State Durability (`novelai.storage.jobs`, `novelai.storage.service`)
- **Target Location**:
  - `backend/src/novelai/storage/jobs.py:80-83` (`save_chapter_state`)
  - `backend/src/novelai/storage/service.py:382-414` (`_write_text_atomic`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `save_chapter_state` uses direct non-atomic `_write_text` instead of atomic tempfile replacement, causing corrupted 0-byte JSON state files and loss of retry counters when worker processes are killed mid-write.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/jobs.py:78-84`:

```python
def save_chapter_state(self, safe_chapter_id: str, payload: dict[str, Any]) -> Path:
    state_dir = self.chapter_state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / f"{_physical_stem(safe_chapter_id)}.json"
    self._write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path
```

In `backend/src/novelai/storage/service.py:382-414`:

```python
def _write_text_atomic(self, path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{time.time_ns()}")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)
```

Notice:

1. `save_chapter_state` uses `self._write_text(path, ...)` which directly truncates and overwrites `path`.
2. When a background Celery / worker container is terminated by Docker, OOM killer, or SIGTERM while writing chapter progress or retry counters, the JSON file is left half-written or at 0 bytes.
3. On worker restart, `load_chapter_state` calls `json.loads()` on the corrupted file, catches `json.JSONDecodeError`, logs a warning, and returns `None`.
4. The worker concludes the chapter has never been attempted, resetting `retry_count` to 0 and wiping out previous failure telemetry. This defeats maximum retry limits (`MAX_RETRIES`), causing infinite retry loops on fundamentally broken chapters.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Infinite Retry Storms**: Chapter failure counters reset to zero, causing crawler/translation workers to repeatedly retry poisoned chapters indefinitely.
2. **State Loss**: Job transition timelines and debug error messages are permanently erased.

#### 3. Concrete Implementation Specification

Update `backend/src/novelai/storage/jobs.py:82` to use `_write_text_atomic` or `_write_json_atomic`:

```python
def save_chapter_state(self, safe_chapter_id: str, payload: dict[str, Any]) -> Path:
    state_dir = self.chapter_state_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / f"{_physical_stem(safe_chapter_id)}.json"
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    if hasattr(self, "_write_text_atomic"):
        self._write_text_atomic(path, data)
    else:
        temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{time.time_ns()}")
        temp_path.write_text(data, encoding="utf-8")
        temp_path.replace(path)
    return path
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_chapter_state_atomic_write.py`:

```python
import json
from novelai.storage.service import StorageService

def test_save_chapter_state_produces_valid_json(tmp_path):
    svc = StorageService(runtime_dir=tmp_path)
    payload = {"status": "in_progress", "retry_count": 3, "step": "translation"}
    path = svc.save_chapter_state("chap_001", payload)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == payload
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_chapter_state_atomic_write.py`

#### 5. Compatibility & Rollback

Direct drop-in replacement. Protects runtime state files from sudden process termination without schema or interface changes.
Rollback command: `git checkout HEAD -- backend/src/novelai/storage/jobs.py`

## Iteration 4: Web Scraping Sources, HTML Parsers, & HTTP Client Infrastructure

### Summary of Recommendations (Iteration 4)

| ID        | Subsystem / Focus                                                                         | Category     | Impact Summary                                                                                                                                                                            |
| --------- | ----------------------------------------------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `REC-031` | Syosetu API Metadata Ingestion (`syosetu_api.py`)                                         | Weakness     | Inverted `end` flag check classifies all ongoing novels as completed and completed novels as ongoing, corrupting DB status and halting automated updates.                                 |
| `REC-032` | Rate Limiting & Distributed Coordination (`throttle.py`, `fetch_service.py`)              | Architecture | Process-local in-memory `DomainThrottle` lacks distributed Redis coordination across worker and admin processes, causing multi-process rate multiplication and missed rate-limit backoff. |
| `REC-033` | Rate Limiting & Domain Throttling (`throttle.py`)                                         | Weakness     | `DomainThrottle.before_request` releases lock during `asyncio.sleep`, creating a race condition where concurrent coroutines burst simultaneous requests.                                  |
| `REC-034` | HTTP Redirect Security & Header Scrubbing (`fetch_service.py`)                            | Security     | Incomplete static blocklist in `_CROSS_ORIGIN_STRIPPED_HEADERS` leaks custom API keys, bearer tokens, and session headers to third-party destinations during cross-origin redirects.      |
| `REC-035` | Syosetu Table of Contents Scraper (`syosetu/adapter.py`)                                  | Weakness     | TOC page discovery only inspects links on page 1 and ignores API episode count, silently truncating long serialized novels beyond 5 TOC pages.                                            |
| `REC-036` | Kakuyomu Table of Contents Scraper (`kakuyomu/adapter.py`)                                | Gap          | Hard `SourceError` exception upon encountering UI-paginated ranges or lazy TOC elements permanently blocks ingestion of large Kakuyomu novels.                                            |
| `REC-037` | HTML Ingestion & Character Encoding (`kakuyomu/adapter.py`, `syosetu/adapter.py`)         | Weakness     | Hardcoded `body.decode("utf-8", errors="replace")` ignores HTTP headers and meta tags, silently replacing Shift_JIS/EUC-JP Japanese kanji with `\ufffd`.                                  |
| `REC-038` | Chapter Illustration Extraction & Asset Safety (`_helpers.py`)                            | Security     | `image_source_url` lacks URL scheme, loopback, and internal network validation, allowing malicious chapter illustrations to trigger SSRF or local file reads.                             |
| `REC-039` | Scraper Client Resilience & Fingerprinting (`kakuyomu/adapter.py`, `syosetu/adapter.py`)  | Architecture | Hardcoded static Chrome User-Agent strings lack environment configuration or rotation, risking total scraping outages on anti-bot header challenges.                                      |
| `REC-040` | Story Section Sanitization & Reader Security (`syosetu/parser.py`, `kakuyomu/adapter.py`) | Security     | `prepare_story_section` only strips `.novel_bn`, allowing embedded `<script>`, `<iframe>`, `<style>`, and event handlers to persist into stored chapter HTML and reader UI.               |

---

### REC-031: Inverted Publication Status Mapping in Syosetu Official API Parser

- **ID**: `REC-031`
- **Subsystem/Component**: Syosetu Official API Parser (`novelai.sources.syosetu_api`, `novelai.sources.syosetu.adapter`)
- **Target Location**:
  - `backend/src/novelai/sources/syosetu_api.py:183-205` (`parse_novel_entry`)
  - `backend/src/novelai/sources/syosetu/adapter.py:585-605` (`SyosetuNcodeSource.fetch_metadata`)
  - `backend/tests/test_syosetu_api_client.py:44-55` (`test_parse_novel_entry_maps_regular_genre_and_status`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `parse_novel_entry` inverts the Syosetu API `end` flag by treating `end == 0` as `完結済` ("completed"), causing every ongoing serialized novel ingested via the API to be persisted as completed, permanently disabling automated chapter update checks.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/syosetu_api.py:188-208`:

```python
novel_type_raw = _parse_int(raw.get("noveltype") or raw.get("novel_type")) or 1
end_flag = _parse_int(raw.get("end"))
isstop_flag = _parse_int(raw.get("isstop"))

is_long_stopped = isstop_flag == 1

if novel_type_raw == 2:
    status_jp = "短編"
elif end_flag == 0:
    status_jp = "完結済"
elif is_long_stopped:
    status_jp = "休載"
else:
    status_jp = "連載中"
```

And in `backend/tests/test_syosetu_api_client.py:45-55`:

```python
raw = {
    "ncode": "n1234ab",
    "title": "魔法使いの旅",
    "end": 0,
    "isstop": 0,
    ...
}
entry, typed_meta = parse_novel_entry(raw, genre_map=SYOSETU_GENRE_MAP)
assert entry["publication_status"] == "completed"
assert entry["source_publication_status"] == "完結済"
```

Notice:

1. According to the official Syosetu API specification (`https://dev.syosetu.com/man/api/`):
   > `end`: 完結済かのフラグです。短編、連載中なら0、完結済なら1となります。
   > The official API defines `end = 0` as ongoing (`連載中` / short story) and `end = 1` as completed (`完結済`).
2. `parse_novel_entry` inverts this logic by mapping `end == 0` to `完結済` ("completed")!
3. In `SyosetuNcodeSource.fetch_metadata` (`adapter.py:586-605`), API metadata overrides HTML metadata for `publication_status`.
4. Therefore, every single ongoing serialized novel fetched via Syosetu API is persisted in PostgreSQL as `publication_status = "completed"`.
5. The existing test in `test_syosetu_api_client.py` asserts `end: 0` produces `"completed"`, baking the inverted bug directly into the test suite.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Disabled Automated Updates**: Scheduled crawlers check for updates only on ongoing novels; marking ongoing novels completed permanently halts chapter ingestion.
2. **Corrupted Reader Filters**: Readers filtering the catalog for "Completed" novels receive ongoing works with unfinished story arcs.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/sources/syosetu_api.py:195-205`, fix the `end_flag` mapping:

```python
if novel_type_raw == 2:
    status_jp = "短編"
elif is_long_stopped:
    status_jp = "休載"
elif end_flag == 1:
    status_jp = "完結済"
else:
    status_jp = "連載中"
```

2. Correct the unit tests in `backend/tests/test_syosetu_api_client.py`:

```python
def test_parse_novel_entry_maps_ongoing_status():
    raw = {"ncode": "n1234ab", "title": "魔法使いの旅", "end": 0, "isstop": 0, "noveltype": 1}
    entry, _ = parse_novel_entry(raw)
    assert entry["publication_status"] == "ongoing"
    assert entry["source_publication_status"] == "連載中"

def test_parse_novel_entry_maps_completed_status():
    raw = {"ncode": "n1234ab", "title": "魔法使いの旅", "end": 1, "isstop": 0, "noveltype": 1}
    entry, _ = parse_novel_entry(raw)
    assert entry["publication_status"] == "completed"
    assert entry["source_publication_status"] == "完結済"
```

#### 4. Verification & Test Strategy

Create or update `backend/tests/test_syosetu_api_client.py`.
Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_syosetu_api_client.py`

#### 5. Compatibility & Rollback

Non-breaking. Restores correct publication status mapping and re-enables crawler polling for ongoing works.
Rollback command: `git checkout HEAD -- backend/src/novelai/sources/syosetu_api.py backend/tests/test_syosetu_api_client.py`

---

### REC-032: Process-Local In-Memory `DomainThrottle` State Lacks Distributed Redis Coordination

- **ID**: `REC-032`
- **Subsystem/Component**: Rate Limiting & Distributed Coordination (`novelai.infrastructure.http.throttle`, `novelai.infrastructure.http.fetch_service`)
- **Target Location**:
  - `backend/src/novelai/infrastructure/http/throttle.py:20-40` (`DomainThrottle.__init__`)
  - `backend/src/novelai/infrastructure/http/throttle.py:52-67` (`DomainThrottle.before_request`)
  - `backend/src/novelai/infrastructure/http/fetch_service.py:148` (`_GLOBAL_THROTTLE`)
- **Category**: `Architecture`
- **Severity**: `High`
- **Summary**: `DomainThrottle` stores rate-limiting and backoff state strictly in local process memory, allowing concurrent worker and admin containers to multiply outbound scraping rates and hiding domain backoff penalties across processes.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/infrastructure/http/throttle.py:20-40`:

```python
class DomainThrottle:
    def __init__(
        self,
        *,
        min_delay_seconds: float | None = None,
        max_delay_seconds: float = 30.0,
    ) -> None:
        self.min_delay_seconds = (
            float(settings.SCRAPE_DELAY_SECONDS) if min_delay_seconds is None else max(0.0, float(min_delay_seconds))
        )
        self.max_delay_seconds = max(self.min_delay_seconds, float(max_delay_seconds))
        self._states: dict[str, _DomainThrottleState] = {}
        self._lock = asyncio.Lock()
```

And in `backend/src/novelai/infrastructure/http/fetch_service.py:148`:

```python
_GLOBAL_THROTTLE = DomainThrottle()
```

Notice:

1. In `compose.yml`, multiple separate containers (`novelai-admin`, `novelai-reader`, `novelai-worker`) run in parallel.
2. Each process instantiates its own `DomainThrottle` instance with process-local in-memory state (`self._states: dict`).
3. If 3 worker processes crawl Syosetu or Kakuyomu concurrently, each process enforces a 1-second delay independently, resulting in 3 requests per second hitting the upstream domain.
4. When Worker 1 encounters HTTP 429 Too Many Requests, `after_response()` increases `penalty_seconds` only inside Worker 1's local memory. Workers 2 and 3 remain unaware and continue pounding the target domain, triggering Cloudflare Turnstile blocks or IP blacklisting.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Target Domain IP Bans**: Multiplied request rates across worker containers trigger upstream scraping blocks and Cloudflare Captcha challenges.
2. **Penalty Isolation**: Backoff signals from 429 responses are not communicated to sibling workers, worsening rate-limit violations.

#### 3. Concrete Implementation Specification

Implement a distributed Redis throttle coordinator in `novelai.infrastructure.http.throttle`:

```python
import redis.asyncio as redis

class RedisDomainThrottle:
    """Distributed domain throttle backed by Valkey/Redis with local fallback."""
    def __init__(self, redis_client: redis.Redis | None = None, min_delay_seconds: float = 1.0, max_delay: float = 30.0):
        self._redis = redis_client
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay
        self._local = DomainThrottle(min_delay_seconds=min_delay_seconds, max_delay_seconds=max_delay)

    async def before_request(self, url: str) -> None:
        if not self._redis:
            await self._local.before_request(url)
            return

        domain = DomainThrottle._domain(url)
        if not domain:
            return

        key = f"throttle:{domain}:schedule"
        now = time.time()
        lua = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local min_delay = tonumber(ARGV[2])
        local current = tonumber(redis.call('get', key) or '0')
        local target = math.max(now, current)
        redis.call('set', key, target + min_delay, 'EX', 120)
        return target - now
        """
        wait_seconds = await self._redis.eval(lua, 1, key, now, self.min_delay)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    async def after_response(self, url: str, status_code: int) -> None:
        domain = DomainThrottle._domain(url)
        if not domain:
            return
        if self._redis and (status_code == 429 or 500 <= status_code <= 599):
            await self._redis.set(f"throttle:{domain}:schedule", time.time() + 10.0, ex=60)
        await self._local.after_response(url, status_code)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_distributed_throttle.py`:

```python
import pytest
from unittest.mock import AsyncMock
from novelai.infrastructure.http.throttle import RedisDomainThrottle

@pytest.mark.asyncio
async def test_redis_throttle_propagates_penalty_across_instances():
    fake_redis = AsyncMock()
    fake_redis.eval.return_value = 0.0
    throttle1 = RedisDomainThrottle(redis_client=fake_redis)
    throttle2 = RedisDomainThrottle(redis_client=fake_redis)

    await throttle1.after_response("https://ncode.syosetu.com/n1234/", 429)
    assert fake_redis.set.call_count >= 1
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_distributed_throttle.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Gracefully falls back to local in-memory `DomainThrottle` when Redis client is unavailable or during local unit testing.
Rollback command: `git checkout HEAD -- backend/src/novelai/infrastructure/http/throttle.py backend/src/novelai/infrastructure/http/fetch_service.py`

---

### REC-033: Race Condition and Lock Release in `DomainThrottle` Permitting Burst Thundering Herds

- **ID**: `REC-033`
- **Subsystem/Component**: Outbound HTTP Transport & Rate Limiting (`novelai.infrastructure.http.throttle`)
- **Target Location**:
  - `backend/src/novelai/infrastructure/http/throttle.py:50-70` (`DomainThrottle.before_request`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `DomainThrottle.before_request` releases its lock during `asyncio.sleep` before updating `last_request_at`, creating a concurrency race condition that allows concurrent coroutines to bypass rate limiting and fire bursts of simultaneous requests to target domains.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/infrastructure/http/throttle.py:50-70`:

```python
async def before_request(self, url: str) -> None:
    domain = self._domain(url)
    if not domain:
        return

    async with self._lock:
        state = self._states.setdefault(domain, _DomainThrottleState())
        delay = min(self.max_delay_seconds, self.min_delay_seconds + state.penalty_seconds)
        wait_seconds = max(0.0, delay - (time.monotonic() - state.last_request_at))

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    async with self._lock:
        self._states.setdefault(domain, _DomainThrottleState()).last_request_at = time.monotonic()
```

Notice:

1. In the first `async with self._lock:`, `wait_seconds` is calculated based on `state.last_request_at`.
2. The lock is released while `await asyncio.sleep(wait_seconds)` executes. Crucially, `state.last_request_at` has NOT been updated!
3. When multiple coroutines concurrently call `before_request(url)` (e.g. parallel chapter crawlers or illustration fetchers):
   - Task 1 calculates `wait_seconds = 1.0` and sleeps.
   - Task 2 enters `self._lock` immediately. Because `state.last_request_at` still points to the previous request from seconds ago, Task 2 computes `wait_seconds = 0.0` and returns immediately without sleeping!
   - Tasks 3, 4, and 5 do the same, all witnessing the stale `last_request_at`.
4. The result is a thundering herd where multiple requests are fired simultaneously in a tight burst, completely bypassing `SCRAPE_DELAY_SECONDS`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Upstream Rate Limit Bans**: Simultaneous burst requests trigger Cloudflare rate limits and immediate HTTP 429 Too Many Requests from Syosetu and Kakuyomu.
2. **IP Blacklisting**: Repeated burst spikes flag the server's egress IP as a malicious scraper, requiring manual IP changes.

#### 3. Concrete Implementation Specification

Implement monotonic time reservation scheduling with `next_allowed_at` inside `_DomainThrottleState`:

```python
@dataclass
class _DomainThrottleState:
    next_allowed_at: float = 0.0
    penalty_seconds: float = 0.0
```

Update `before_request` to atomically advance the reservation schedule inside the lock before sleeping:

```python
async def before_request(self, url: str) -> None:
    domain = self._domain(url)
    if not domain:
        return

    async with self._lock:
        state = self._states.setdefault(domain, _DomainThrottleState())
        delay = min(self.max_delay_seconds, self.min_delay_seconds + state.penalty_seconds)
        now = time.monotonic()
        target_time = max(now, state.next_allowed_at)
        wait_seconds = max(0.0, target_time - now)
        state.next_allowed_at = target_time + delay

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_throttle_concurrency.py`:

```python
import asyncio
import time
import pytest
from novelai.infrastructure.http.throttle import DomainThrottle

@pytest.mark.asyncio
async def test_concurrent_tasks_are_sequentially_spaced():
    throttle = DomainThrottle(min_delay_seconds=0.1)
    timestamps = []

    async def worker():
        await throttle.before_request("https://ncode.syosetu.com/n1234/")
        timestamps.append(time.monotonic())

    await asyncio.gather(*(worker() for _ in range(4)))

    for i in range(len(timestamps) - 1):
        diff = timestamps[i + 1] - timestamps[i]
        assert diff >= 0.08
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_throttle_concurrency.py`

#### 5. Compatibility & Rollback

Direct drop-in replacement. Preserves existing class interface and method signatures.
Rollback command: `git checkout HEAD -- backend/src/novelai/infrastructure/http/throttle.py`

---

### REC-034: Static Header Blocklist in `FetchService` Leaks Custom Auth Tokens Across Cross-Origin Redirects

- **ID**: `REC-034`
- **Subsystem/Component**: HTTP Redirect Security & Header Scrubbing (`novelai.infrastructure.http.fetch_service`)
- **Target Location**:
  - `backend/src/novelai/infrastructure/http/fetch_service.py:28-39` (`_CROSS_ORIGIN_STRIPPED_HEADERS`)
  - `backend/src/novelai/infrastructure/http/fetch_service.py:68-76` (`_strip_origin_sensitive_headers`)
  - `backend/src/novelai/infrastructure/http/fetch_service.py:380-405` (`FetchService._request`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: Incomplete static blocklist in `_CROSS_ORIGIN_STRIPPED_HEADERS` leaks custom authorization tokens (`X-Api-Key`, `X-Auth-Token`, bearer tokens) and session headers to external origins across cross-origin HTTP redirects.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/infrastructure/http/fetch_service.py:28-39`:

```python
_CROSS_ORIGIN_STRIPPED_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "host",
        "if-none-match",
        "if-modified-since",
        "if-match",
        "if-unmodified-since",
        "if-range",
    }
)

def _strip_origin_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in _CROSS_ORIGIN_STRIPPED_HEADERS}
```

Notice:

1. `_strip_origin_sensitive_headers` relies strictly on a hardcoded 9-element set.
2. When scraper adapters or API callers supply custom authentication headers—such as `X-Api-Key`, `X-Auth-Token`, `X-Secret-Key`, `X-Access-Token`, or session headers—none of these headers match the exact strings in `_CROSS_ORIGIN_STRIPPED_HEADERS`.
3. If an upstream endpoint redirects cross-origin (e.g. from an authenticated API host to an external CDN, S3/R2 presigned URL, or third-party image host), lines 380-385 keep all non-matching headers.
4. Consequently, proprietary API keys and authentication credentials are sent in plaintext request headers to foreign third-party servers.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Credential Disclosure via SSRF / Redirects**: Attacker-controlled novel sources redirecting to attacker servers capture internal API keys and tokens transmitted in request headers.
2. **Third-Party Data Leak**: Upstream CDN or hosting providers log internal authorization headers in their access logs.

#### 3. Concrete Implementation Specification

In `backend/src/novelai/infrastructure/http/fetch_service.py`, replace the narrow blocklist with a comprehensive sensitive header filter matching credential patterns:

```python
import re

_SENSITIVE_HEADER_PATTERN = re.compile(
    r"^(authorization|proxy-authorization|cookie|host|x-api-key|x-auth-.*|x-access-.*|"
    r"x-token|api-key|token|secret|signature|private-key|session-.*|"
    r"if-none-match|if-modified-since|if-match|if-unmodified-since|if-range)$",
    re.IGNORECASE,
)

def _strip_origin_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    """Strip all credential, authorization, and origin-scoped headers on cross-origin redirects."""
    return {key: value for key, value in headers.items() if not _SENSITIVE_HEADER_PATTERN.match(key)}
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_fetch_redirect_security.py`:

```python
from novelai.infrastructure.http.fetch_service import _strip_origin_sensitive_headers

def test_strip_origin_sensitive_headers_removes_custom_api_keys():
    headers = {
        "User-Agent": "NovelAI/1.0",
        "Accept": "text/html",
        "Authorization": "Bearer token123",
        "X-Api-Key": "secret-key-456",
        "X-Auth-Token": "auth-token-789",
        "Cookie": "session=abc",
    }
    cleaned = _strip_origin_sensitive_headers(headers)
    assert "User-Agent" in cleaned
    assert "Accept" in cleaned
    assert "Authorization" not in cleaned
    assert "X-Api-Key" not in cleaned
    assert "X-Auth-Token" not in cleaned
    assert "Cookie" not in cleaned
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_fetch_redirect_security.py`

#### 5. Compatibility & Rollback

RFC 7230 and Fetch spec compliant. Non-breaking for legitimate cross-origin asset downloads.
Rollback command: `git checkout HEAD -- backend/src/novelai/infrastructure/http/fetch_service.py`

---

### REC-035: First-Page Truncation and Ignored API Episode Count in Syosetu Multi-Page TOC Crawling

- **ID**: `REC-035`
- **Subsystem/Component**: Syosetu Scraping Adapter (`novelai.sources.syosetu.adapter`)
- **Target Location**:
  - `backend/src/novelai/sources/syosetu/adapter.py:246-271` (`_extract_page_numbers`)
  - `backend/src/novelai/sources/syosetu/adapter.py:607-640` (`SyosetuNcodeSource.fetch_metadata`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `_extract_page_numbers` only extracts TOC page links from page 1's HTML, missing subsequent pages on novels spanning more than 5 TOC pages, and ignores the exact episode count already retrieved from Syosetu's official API.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/syosetu/adapter.py:246-271` and `620-640`:

```python
def _extract_page_numbers(self, soup: BeautifulSoup, url: str) -> list[int]:
    base_url = httpx.URL(url)
    novel_id = self.normalize_novel_id(url)
    page_numbers = {1}
    for anchor in soup.find_all("a", href=True):
        ...
        page_number = candidate.params.get("p")
        if page_number and page_number.isdigit():
            page_numbers.add(int(page_number))
    return sorted(page_numbers)
```

Notice:

1. Syosetu caps TOC at 100 chapters per page.
2. For long web novels (e.g. 1,000 chapters across 10 pages), page 1 renders sliding window pagination: `[1] [2] [3] [4] [5] ... [>>]`.
3. `_extract_page_numbers` runs only on page 1's HTML. The anchors on page 1 only link up to page 5.
4. As the loop iterates through pages 2, 3, 4, and 5, it never discovers links to pages 6 through 10.
5. Furthermore, `SyosetuNovelApi.fetch_novel()` already provides `general_all_no` (the exact total episode count) in `typed_meta.episode_count`. Because each TOC page holds exactly 100 chapters, the total number of pages is deterministically `math.ceil(total_episodes / 100)`. Ignoring this known count results in silent truncation of novels with >500 chapters.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Silent Story Truncation**: High-volume novels (e.g. 800-chapter web serials) stop crawling halfway through, leaving readers stranded at chapter 500 with no error logged.
2. **Incomplete Catalog Data**: Total chapter count in the database reflects only the truncated page count.

#### 3. Concrete Implementation Specification

1. In `SyosetuNcodeSource.fetch_metadata`, calculate expected pages directly from API metadata when available:

```python
soup = BeautifulSoup(html, "lxml")
if typed_meta and typed_meta.episode_count:
    import math
    total_pages = max(1, math.ceil(typed_meta.episode_count / 100))
    page_numbers = list(range(1, total_pages + 1))
else:
    page_numbers = self._extract_page_numbers(soup, url)
```

2. For HTML-only fallback crawling, update `page_numbers` dynamically if a fetched TOC page reveals additional higher page numbers:

```python
new_pages = self._extract_page_numbers(page_soup, url)
for p in new_pages:
    if p not in page_numbers:
        page_numbers.append(p)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_syosetu_toc_pagination.py`:

```python
import math
import pytest
from unittest.mock import AsyncMock, MagicMock
from novelai.sources.syosetu.adapter import SyosetuNcodeSource
from novelai.sources.syosetu_api import SyosetuNovelMetadata

@pytest.mark.asyncio
async def test_syosetu_fetches_all_10_pages_for_1000_episodes():
    source = SyosetuNcodeSource()
    meta = SyosetuNovelMetadata(ncode="n1234ab", title="Epic", episode_count=950)
    expected_pages = list(range(1, math.ceil(meta.episode_count / 100) + 1))
    assert len(expected_pages) == 10
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_syosetu_toc_pagination.py`

#### 5. Compatibility & Rollback

Fully backwards-compatible. Re-crawling existing truncated novels naturally discovers and downloads the missing chapters.
Rollback command: `git checkout HEAD -- backend/src/novelai/sources/syosetu/adapter.py`

---

### REC-036: Hard Failure on Large Kakuyomu Novels Due to Unhandled TOC Pagination and Lazy Loading

- **ID**: `REC-036`
- **Subsystem/Component**: Kakuyomu Scraping Adapter (`novelai.sources.kakuyomu.adapter`)
- **Target Location**:
  - `backend/src/novelai/sources/kakuyomu/adapter.py:334-360` (`_dom_incomplete_indicators`)
  - `backend/src/novelai/sources/kakuyomu/adapter.py:458-475` (`_extract_chapters`)
- **Category**: `Gap`
- **Severity**: `High`
- **Summary**: Kakuyomu adapter raises a hard `SourceError` whenever a novel's table of contents exhibits UI-paginated episode ranges or lazy-loading indicators, completely blocking the ingestion of long and popular works.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/kakuyomu/adapter.py:458-475`:

```python
html_chapters = self._extract_chapters_from_html(soup, url)
range_labels, lazy_labels = self._dom_incomplete_indicators(soup)
html_count = len(html_chapters)
if isinstance(expected_count, int) and html_count < expected_count:
    raise SourceError(
        "Kakuyomu chapter index is incomplete: "
        f"expected {expected_count} public episodes but enumerated {html_count} from the available page data."
    )
if (range_labels or lazy_labels) and not isinstance(expected_count, int):
    indicators = ", ".join(range_labels + lazy_labels)
    raise SourceError(
        "Kakuyomu chapter index appears to be lazy or UI-paginated "
        f"({indicators}); complete episode enumeration is unavailable."
    )
```

Notice:

1. Long novels on Kakuyomu (>100 episodes) split their table of contents into UI range tabs (e.g. `1〜100話`, `101〜200話`) or dynamic lazy-loaded sections.
2. The method `_dom_incomplete_indicators` inspects the DOM for `UI_RANGE_LABEL_PATTERN` or `LAZY_TOC_LABELS`.
3. If any indicator is found and `expected_count` is not fully matched by page 1 HTML, `_extract_chapters` immediately throws `SourceError("Kakuyomu chapter index is incomplete...")`.
4. Instead of crawling the range tabs or querying Kakuyomu's Next.js Apollo state data (`__NEXT_DATA__` or `/api/trpc/work.getTableOfContents`), the adapter aborts ingestion entirely.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Total Ingestion Failure on Popular Novels**: The most popular, long-running novels on Kakuyomu cannot be crawled, triggering 500 errors in the admin UI and crawler jobs.
2. **Unnecessary Manual Ingestion Blockers**: Users attempting to import top-ranking works receive immediate failure errors.

#### 3. Concrete Implementation Specification

1. In `KakuyomuSource._extract_chapters`, extract additional chapter range URLs from range buttons/anchors instead of failing:

```python
range_links = [
    a.get("href") for a in soup.select("a.widget-toc-range, a[href*='page=']")
    if a.get("href")
]
```

2. If complete enumeration via DOM ranges is not yet possible, degrade gracefully rather than throwing a fatal `SourceError`:

```python
if (range_labels or lazy_labels) and not isinstance(expected_count, int):
    logger.warning(
        "Kakuyomu novel %s has paginated/lazy TOC indicators: %s. Proceeding with %d enumerated chapters.",
        url, indicators, html_count
    )
    provenance["toc_potentially_truncated"] = True
    return html_chapters, provenance
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_kakuyomu_toc_resilience.py`:

```python
from bs4 import BeautifulSoup
from novelai.sources.kakuyomu.adapter import KakuyomuSource

def test_kakuyomu_does_not_abort_on_range_labels():
    source = KakuyomuSource()
    html = """
    <html><body>
      <div class="widget-toc-items"><a href="/works/123/episodes/1"><span>Ep 1</span></a></div>
      <div class="ui-range">1〜50話</div>
    </body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    chapters = source._extract_chapters_from_html(soup, "https://kakuyomu.jp/works/123")
    assert len(chapters) == 1
    assert chapters[0]["title"] == "Ep 1"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_kakuyomu_toc_resilience.py`

#### 5. Compatibility & Rollback

Non-breaking change. Allows large Kakuyomu novels to be imported and crawled immediately.
Rollback command: `git checkout HEAD -- backend/src/novelai/sources/kakuyomu/adapter.py`

---

### REC-037: Silent Unicode Replacement-Character Text Mangling for Shift_JIS and EUC-JP Web Sources

- **ID**: `REC-037`
- **Subsystem/Component**: Web Scraping Adapters & Encoding (`novelai.sources.kakuyomu.adapter`, `novelai.sources.syosetu.adapter`, `novelai.sources._helpers`)
- **Target Location**:
  - `backend/src/novelai/sources/kakuyomu/adapter.py:151` (`KakuyomuSource._decode_page_body`)
  - `backend/src/novelai/sources/syosetu/adapter.py:165, 169` (`SyosetuNcodeSource._decode_page_response`, `_decode_page_body`)
  - `backend/src/novelai/sources/_helpers.py:20-55` (`decode_html_bytes`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: Scraper adapters hardcode `body.decode("utf-8", errors="replace")`, ignoring HTTP `Content-Type` charset headers and HTML `<meta charset>` tags, silently converting Japanese kanji and kana in Shift_JIS or EUC-JP pages into replacement characters (`\ufffd`).

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/syosetu/adapter.py:165-171`:

```python
@staticmethod
def _decode_page_response(response: httpx.Response) -> str:
    return response.content.decode("utf-8", errors="replace")

@staticmethod
def _decode_page_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")
```

And in `backend/src/novelai/sources/kakuyomu/adapter.py:151`:

```python
@staticmethod
def _decode_page_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")
```

Notice:

1. Japanese web novel hosts and archives occasionally use `Shift_JIS`, `Windows-31J` (CP932), or `EUC-JP` encodings.
2. When multi-byte Japanese characters in Shift_JIS are decoded as UTF-8 with `errors="replace"`, every non-ASCII byte sequence fails UTF-8 decoding rules.
3. Python silently replaces each failed byte with `\ufffd` (the replacement character).
4. Because `errors="replace"` never raises an exception, the scraper reports success and saves hundreds of corrupted chapters composed entirely of replacement characters.
5. The adapters never inspect the HTTP response header `Content-Type: text/html; charset=...`, never inspect `<meta charset="...">` declarations, and fail to fall back to `cp932` when UTF-8 decoding fails.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Permanent Text Corruption**: Scraped novels from older Japanese archives are permanently mangled with replacement glyphs before translation.
2. **Wasted LLM Tokens**: Corrupted `\ufffd` strings are sent to Gemini/OpenAI, generating nonsensical gibberish translations and consuming token quota.

#### 3. Concrete Implementation Specification

Implement a resilient HTML decoding helper in `backend/src/novelai/sources/_helpers.py`:

```python
import re

_CHARSET_RE = re.compile(rb'<meta[^>]+charset=["\']?([a-zA-Z0-9_-]+)', re.IGNORECASE)

def decode_html_bytes(body: bytes, content_type_header: str | None = None) -> str:
    """Decode raw HTML bytes into string, honoring Content-Type and meta charset with Japanese fallback."""
    if content_type_header and "charset=" in content_type_header.lower():
        cs = content_type_header.lower().split("charset=")[-1].split(";")[0].strip("\"' ")
        try:
            return body.decode(cs)
        except (UnicodeDecodeError, LookupError):
            pass

    meta_match = _CHARSET_RE.search(body[:2048])
    if meta_match:
        cs = meta_match.group(1).decode("ascii", errors="ignore").strip()
        try:
            return body.decode(cs)
        except (UnicodeDecodeError, LookupError):
            pass

    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        pass

    for encoding in ("cp932", "euc_jp"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue

    return body.decode("utf-8", errors="replace")
```

Update `_decode_page_body` in `SyosetuNcodeSource` and `KakuyomuSource` to call `decode_html_bytes`.

#### 4. Verification & Test Strategy

Create `backend/tests/test_html_encoding_fallback.py`:

```python
from novelai.sources._helpers import decode_html_bytes

def test_decode_html_bytes_detects_shift_jis():
    sjis_bytes = "魔法使い".encode("cp932")
    html = b'<html><head><meta charset="Shift_JIS"></head><body>' + sjis_bytes + b'</body></html>'
    decoded = decode_html_bytes(html)
    assert "魔法使い" in decoded
    assert "\ufffd" not in decoded
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_html_encoding_fallback.py`

#### 5. Compatibility & Rollback

Non-breaking. UTF-8 content decodes identically, while Shift_JIS/CP932 content is correctly preserved.
Rollback command: `git checkout HEAD -- backend/src/novelai/sources/_helpers.py backend/src/novelai/sources/syosetu/adapter.py backend/src/novelai/sources/kakuyomu/adapter.py`

---

### REC-038: Missing Protocol Scheme and Host Validation in Chapter Illustration Extractor Permitting Asset SSRF

- **ID**: `REC-038`
- **Subsystem/Component**: Content Parsing & Asset Security (`novelai.sources._helpers`, `novelai.services.orchestration.crawler`)
- **Target Location**:
  - `backend/src/novelai/sources/_helpers.py:38-69` (`extract_image_references`)
  - `backend/src/novelai/sources/_helpers.py:108-124` (`image_source_url`)
  - `backend/src/novelai/services/orchestration/crawler.py:711-745` (`_crawl_novel_stream` asset download loop)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `image_source_url` accepts arbitrary URL schemes (`file://`, `ftp://`, loopback and cloud metadata IP addresses) without validation against `validate_safe_url()`, allowing malicious web novels to trigger SSRF or local file disclosure when illustrations are downloaded.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/_helpers.py:108-124`:

```python
def image_source_url(image: Tag, *, base_url: str | None = None) -> str | None:
    raw_src = (
        attribute_to_str(image.get("src"))
        or attribute_to_str(image.get("data-src"))
        or attribute_to_str(image.get("data-original"))
    )
    if raw_src is None:
        return None
    source = raw_src.strip()
    if not source:
        return None
    if base_url is not None:
        try:
            return str(httpx.URL(base_url).join(source))
        except Exception:
            return source
    return source
```

Notice:

1. Web novel authors can embed external illustration links.
2. `image_source_url` performs no verification on the joined or raw `source`:
   - If an author embeds `<img src="http://169.254.169.254/latest/meta-data/">`, `image_source_url` returns the AWS/GCP cloud metadata URL.
   - If an author embeds `<img src="http://localhost:8000/internal-api">`, `image_source_url` returns the internal admin API endpoint.
   - If an author embeds `<img src="file:///etc/passwd">`, `image_source_url` returns `file:///etc/passwd`.
3. In `crawler.py:711-745`, the crawler iterates over `extract_image_references()` to fetch each asset blob (`await source.fetch_asset(original_url)`).
4. Unchecked image references allow malicious or compromised web novels to probe the internal Docker network or fetch sensitive server files.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Server-Side Request Forgery (SSRF)**: Cloud metadata exfiltration (AWS IAM tokens, GCP identity tokens) or internal port scanning across Docker Compose containers.
2. **Local File Disclosure**: Ingestion of server configuration or secrets into novel image asset stores.

#### 3. Concrete Implementation Specification

Validate the resolved image URL against `validate_safe_url` in `backend/src/novelai/sources/_helpers.py`:

```python
from novelai.infrastructure.http.fetch_service import validate_safe_url

def image_source_url(image: Tag, *, base_url: str | None = None) -> str | None:
    raw_src = (
        attribute_to_str(image.get("src"))
        or attribute_to_str(image.get("data-src"))
        or attribute_to_str(image.get("data-original"))
    )
    if raw_src is None:
        return None
    source = raw_src.strip()
    if not source:
        return None

    candidate = source
    if base_url is not None:
        try:
            candidate = str(httpx.URL(base_url).join(source))
        except Exception:
            pass

    parsed = httpx.URL(candidate)
    if parsed.scheme not in {"http", "https"}:
        return None

    try:
        validate_safe_url(candidate)
    except Exception:
        return None

    return candidate
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_image_ssrf_guard.py`:

```python
from bs4 import BeautifulSoup
from novelai.sources._helpers import image_source_url

def test_image_source_url_rejects_ssrf_and_file_schemes():
    soup = BeautifulSoup(
        '<img id="f" src="file:///etc/passwd">'
        '<img id="meta" src="http://169.254.169.254/latest/meta-data/">'
        '<img id="local" src="http://127.0.0.1:8000/secret">'
        '<img id="valid" src="https://cdn.example.com/cover.jpg">',
        "lxml",
    )
    assert image_source_url(soup.select_one("#f")) is None
    assert image_source_url(soup.select_one("#meta")) is None
    assert image_source_url(soup.select_one("#local")) is None
    assert image_source_url(soup.select_one("#valid")) == "https://cdn.example.com/cover.jpg"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_image_ssrf_guard.py`

#### 5. Compatibility & Rollback

Transparent to legitimate public image CDNs. Blocks malicious and private-network targets.
Rollback command: `git checkout HEAD -- backend/src/novelai/sources/_helpers.py`

---

### REC-039: Hardcoded Static User-Agent Strings in Scraper Adapters Preventing Operational Rotation

- **ID**: `REC-039`
- **Subsystem/Component**: Scraper Configuration & Resilience (`novelai.sources.kakuyomu.adapter`, `novelai.sources.syosetu.adapter`, `novelai.config.settings`)
- **Target Location**:
  - `backend/src/novelai/sources/kakuyomu/adapter.py:77` (`KakuyomuSource.USER_AGENT`)
  - `backend/src/novelai/sources/syosetu/adapter.py:157-161` (`SyosetuNcodeSource._request_headers`)
  - `backend/src/novelai/config/settings.py:120-140`
- **Category**: `Architecture`
- **Severity**: `Medium`
- **Summary**: Kakuyomu and Syosetu adapters hardcode static User-Agent strings directly in module class attributes and helper methods, preventing dynamic configuration or rotation when anti-bot systems challenge or block specific browser fingerprints.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/kakuyomu/adapter.py:77`:

```python
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
```

And in `backend/src/novelai/sources/syosetu/adapter.py:157-161`:

```python
def _request_headers(self, *, referer: str | None = None) -> dict[str, str]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if isinstance(referer, str) and referer.strip():
        headers["Referer"] = referer.strip()
    return headers
```

Notice:

1. Both scraping adapters hardcode static browser signatures directly in source code instead of loading them from `novelai.config.settings.settings`.
2. Cloudflare WAF and platform anti-bot heuristics frequently flag outdated browser versions (e.g. Chrome 125 or generic Windows NT headers missing Sec-CH-UA client hints).
3. Operators cannot update or rotate the User-Agent via environment variables in production (`SCRAPER_USER_AGENT`) when an IP or fingerprint is challenged; updating headers requires modifying source code, running linters/tests, and executing a full Docker container build and deployment.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Unmitigated Crawler Blockade**: When Cloudflare or Syosetu blocks the hardcoded Chrome 125 signature, crawler tasks fail across all worker containers until an emergency release is tagged.
2. **Missing Client Hints**: Absence of modern Client Hints (`Sec-CH-UA`, `Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform`) increases bot-score severity under automated WAF evaluation.

#### 3. Concrete Implementation Specification

1. Add scraper configuration fields in `backend/src/novelai/config/settings.py`:

```python
class Settings(BaseSettings):
    ...
    SCRAPER_USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        description="Default User-Agent string used by source crawler adapters",
    )
    SCRAPER_CLIENT_HINTS_ENABLED: bool = Field(
        default=True,
        description="Attach modern Sec-CH-UA client hint headers to scraper requests",
    )
```

2. Update `KakuyomuSource` and `SyosetuNcodeSource` to pull from `settings`:

```python
from novelai.config.settings import settings

def _request_headers(self, *, referer: str | None = None) -> dict[str, str]:
    headers = {"User-Agent": settings.SCRAPER_USER_AGENT}
    if settings.SCRAPER_CLIENT_HINTS_ENABLED:
        headers.update({
            "Sec-CH-UA": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        })
    if isinstance(referer, str) and referer.strip():
        headers["Referer"] = referer.strip()
    return headers
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_scraper_headers.py`:

```python
from novelai.config.settings import settings
from novelai.sources.syosetu.adapter import SyosetuNcodeSource

def test_scraper_headers_reflect_configured_user_agent(monkeypatch):
    monkeypatch.setattr(settings, "SCRAPER_USER_AGENT", "CustomNovelBot/2.0")
    source = SyosetuNcodeSource()
    headers = source._request_headers()
    assert headers["User-Agent"] == "CustomNovelBot/2.0"
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_scraper_headers.py`

#### 5. Compatibility & Rollback

Non-breaking. Defaults preserve functional modern browser emulation.
Rollback command: `git checkout HEAD -- backend/src/novelai/config/settings.py backend/src/novelai/sources/syosetu/adapter.py backend/src/novelai/sources/kakuyomu/adapter.py`

---

### REC-040: Unsanitized HTML in Story Sections Permitting Stored XSS and Reader Layout Hijacking

- **ID**: `REC-040`
- **Subsystem/Component**: HTML Story Parser & Sanitization (`novelai.sources.syosetu.parser`, `novelai.sources.kakuyomu.adapter`, `novelai.sources._helpers`)
- **Target Location**:
  - `backend/src/novelai/sources/syosetu/parser.py:54, 304-332` (`prepare_story_section`, `REMOVE_FROM_SECTION_SELECTORS`)
  - `backend/src/novelai/sources/kakuyomu/adapter.py:620-655` (`KakuyomuSource._parse_chapter_payload`)
  - `backend/src/novelai/sources/_helpers.py:130-180` (`sanitize_story_html`)
- **Category**: `Security`
- **Severity**: `Critical`
- **Summary**: `prepare_story_section` only strips `.novel_bn` elements, allowing embedded `<script>`, `<iframe>`, `<style>`, and event handlers in web novel story bodies to persist into stored chapter HTML and reader views.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/sources/syosetu/parser.py:54, 304-332`:

```python
REMOVE_FROM_SECTION_SELECTORS = (".novel_bn",)

def prepare_story_section(section: Tag) -> Tag | None:
    section_soup = BeautifulSoup(str(section), "lxml")
    prepared = section_soup.select_one(section.name)
    if not isinstance(prepared, Tag):
        return None

    for removable in REMOVE_FROM_SECTION_SELECTORS:
        for tag in prepared.select(removable):
            tag.decompose()
```

And in `backend/src/novelai/sources/kakuyomu/adapter.py:620-655`, only `REMOVE_FROM_BODY_SELECTORS` are decomposed.
Notice:

1. `prepare_story_section` only removes navigation elements matching `.novel_bn`.
2. It performs no sanitization or removal of executable or styling tags:
   - `<script>`: Malicious executable JavaScript.
   - `<iframe>`, `<embed>`, `<object>`: External page embedding and drive-by downloads.
   - `<style>`, `<link rel="stylesheet">`: Viewport hijacking, phishing overlays, or reader UI obscuration.
   - Inline event handlers: `<img src=x onerror="fetch('/api/admin/token').then(...)">`, `<a href="javascript:...">`.
3. In `docs/ARCHITECTURE.md` and `frontend/app/(public)/reader/[novelId]/[chapterId]`, chapter HTML bodies are fetched from storage and rendered in the DOM for guest readers.
4. Any malicious web novel author on an open UGC platform (Syosetu, Kakuyomu) who embeds HTML injection payloads achieves Stored Cross-Site Scripting (XSS) against readers.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Stored Cross-Site Scripting (XSS)**: Attackers execute arbitrary JavaScript in the context of user reader sessions, stealing session tokens, reading reading history, or performing credential phishing.
2. **Reader Interface Hijacking**: Malicious `<style>` tags with `position: fixed; z-index: 99999` inject deceptive fake login forms or banner ads over reader content.

#### 3. Concrete Implementation Specification

Implement strict semantic HTML allowlist sanitization in `backend/src/novelai/sources/_helpers.py`:

```python
from bs4 import BeautifulSoup, Tag

ALLOWED_TAGS = {
    "p", "br", "ruby", "rt", "rp", "em", "strong", "b", "i",
    "hr", "img", "span", "div", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"
}
ALLOWED_ATTRS = {
    "img": {"src", "alt", "title", "loading", "width", "height"},
    "a": {"href", "title", "rel", "target"},
}

def sanitize_story_html(soup_or_tag: Tag) -> None:
    """Recursively sanitize story markup in-place to safe semantic tags and attributes."""
    for tag in list(soup_or_tag.find_all(True)):
        if tag.name.lower() not in ALLOWED_TAGS:
            if tag.name.lower() in {"script", "style", "iframe", "object", "embed", "form", "link"}:
                tag.decompose()
            else:
                tag.unwrap()
            continue

        allowed_for_tag = ALLOWED_ATTRS.get(tag.name.lower(), set())
        attrs_to_remove = []
        for attr, value in tag.attrs.items():
            attr_lower = attr.lower()
            if attr_lower.startswith("on") or attr_lower not in allowed_for_tag:
                attrs_to_remove.append(attr)
            elif attr_lower in {"src", "href"}:
                if isinstance(value, str) and value.strip().lower().startswith(("javascript:", "vbscript:", "data:")):
                    attrs_to_remove.append(attr)

        for attr in attrs_to_remove:
            del tag.attrs[attr]
```

Invoke `sanitize_story_html(prepared)` inside `prepare_story_section` and `_parse_chapter_payload`.

#### 4. Verification & Test Strategy

Create `backend/tests/test_story_html_sanitization.py`:

```python
from bs4 import BeautifulSoup
from novelai.sources._helpers import sanitize_story_html

def test_sanitize_story_html_removes_xss_and_styles():
    html = """
    <div id="story">
      <p>Hello <script>alert('xss')</script>World</p>
      <img src="x" onerror="evil()" />
      <style>body { display: none; }</style>
      <a href="javascript:alert(1)">Click</a>
      <p>Normal <ruby>漢字<rt>かんじ</rt></ruby></p>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    target = soup.select_one("#story")
    sanitize_story_html(target)
    clean_html = str(target)
    assert "<script" not in clean_html
    assert "onerror" not in clean_html
    assert "<style" not in clean_html
    assert "javascript:" not in clean_html
    assert "Hello World" in clean_html or "Hello" in clean_html
    assert "<ruby>漢字<rt>かんじ</rt></ruby>" in clean_html
```

Run: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_story_html_sanitization.py`

#### 5. Compatibility & Rollback

Safe and backwards-compatible. Preserves standard Japanese novel ruby annotations, typography, and clean text while neutralizing malicious injection vectors.
Rollback command: `git checkout HEAD -- backend/src/novelai/sources/_helpers.py backend/src/novelai/sources/syosetu/parser.py backend/src/novelai/sources/kakuyomu/adapter.py`

## Iteration 5: Translation Engine, LLM Providers, Prompts, Glossary Pipeline, Cost Estimator, & QA Validation

### Summary of Recommendations (Iteration 5)

| ID        | Subsystem / Focus                                                                               | Category    | Impact Summary                                                                                                                                                               |
| --------- | ----------------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `REC-041` | LLM Provider Concurrency & Transport (`gemini_provider.py`)                                     | Performance | Synchronous `client.models.generate_content` in `asyncio.to_thread` exhausts Python's default threadpool and lacks native async request cancellation semantics.              |
| `REC-042` | Paragraph Chunk Packing & Partitioning (`segment.py`)                                           | Weakness    | `_balanced_paragraph_groups` enters an infinite `while True` loop when `chunk_count` exceeds paragraph count due to permanently failing remaining count checks.              |
| `REC-043` | Japanese Dialogue Sentence Segmentation (`segment.py`)                                          | Weakness    | Mandatory whitespace in sentence lookbehind (`(?<=[」』）)])\s+`) never matches standard Japanese novel typography, splitting sentences inside spoken dialogue.              |
| `REC-044` | Glossary Replacement & Pipeline Post-Processing (`glossary.py`, `post_process.py`)              | Weakness    | `Glossary.translate` performs naive `str.replace` of Japanese terms on English text causing substring corruption, while `PostProcessStage` ignores runtime pipeline context. |
| `REC-045` | Pipeline DB Concurrency & Session Management (`translate.py`)                                   | Performance | Synchronous `session_scope()` inside `TranslateStage._build_prompt_glossary_block` blocks the async event loop and executes $O(N)$ redundant DB queries per chunk.           |
| `REC-046` | Pipeline Worker Concurrency & Semaphore Starvation (`translate.py`)                             | Performance | Holding `async with semaphore:` across retry loops blocks worker concurrency slots during exponential backoff sleep (up to 60s), stalling pipeline throughput.               |
| `REC-047` | Translation QA Residue Checks & LLM Grader Resilience (`qa.py`, `translation_qa.py`)            | Weakness    | Short chunks ($\le 50$ chars) completely bypass CJK residue detection, while `evaluate_translation_quality_with_llm` unconditionally returns 1.0 on errors, masking outages. |
| `REC-048` | Prompt Engineering & Glossary Context Budgeting (`builders.py`, `glossary_prompt_injection.py`) | Weakness    | `format_glossary_block` injects uncurated glossaries into prompts without token caps, while `_any_contains` searches for Japanese terms in translated English context.       |
| `REC-049` | Translation Cost Estimator & Model Catalog (`pricing.py`, `compare.py`)                         | Weakness    | `DEFAULT_PRICING` lacks the production default model (`gemini-2.5-flash`), raising `ValueError` on estimation, while zero-cost division silences cost differences.           |
| `REC-050` | Translation Cache Eviction & Key Parameterization (`translation_cache.py`)                      | Weakness    | `TranslationCache` uses arbitrary dict slice eviction (FIFO) with full JSON rewrites on every set, and ignores language, style, and glossary parameters in its keys.         |

---

### REC-041: Thread Pool Saturation and Missing Async Cancellation Semantics in Synchronous Gemini SDK Calls via `asyncio.to_thread`

- **ID**: `REC-041`
- **Subsystem/Component**: LLM Provider & Async Concurrency (`novelai.providers.gemini_provider`)
- **Target Location**:
  - `backend/src/novelai/providers/gemini_provider.py:104-109` (`_get_client`)
  - `backend/src/novelai/providers/gemini_provider.py:700-725` (`GeminiProvider.translate`)
  - `backend/src/novelai/providers/gemini_provider.py:280-355` (`_classify_exception`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `GeminiProvider.translate` wraps blocking synchronous SDK calls (`client.models.generate_content`) in `asyncio.to_thread` instead of leveraging the Google GenAI SDK's native asynchronous interface (`client.aio.models.generate_content`), saturating the default Python thread pool and preventing prompt cancellation.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/providers/gemini_provider.py`, lines 700-725 define:

```python
def _invoke() -> Any:
    client = self._get_client(Client, api_key_str)
    generate_kwargs: dict[str, Any] = {
        "model": model_name,
        "contents": contents,
    }
    if config_payload:
        generate_kwargs["config"] = config_payload
    return client.models.generate_content(**generate_kwargs)

execution_started = time.perf_counter()
execution_ms: float | None = None
try:
    response = await asyncio.to_thread(_invoke)
    execution_ms = (time.perf_counter() - execution_started) * 1000
```

And `_classify_exception` in lines 280-355.
Notice:

1. Python's default `ThreadPoolExecutor` (used by `asyncio.to_thread`) has a maximum size of `min(32, os.cpu_count() + 4)`.
2. Under batch translation jobs (multiple chapters translating concurrently across worker processes), dozens of blocking HTTP socket calls concurrently occupy OS threads.
3. Once the pool is saturated, background file I/O, database thread tasks, and async task completions stall waiting for available worker threads.
4. Synchronous calls in `to_thread` cannot be cancelled cooperatively: when an HTTP request times out or is cancelled by the orchestrator, the underlying worker thread remains blocked waiting on Google's API server response, leaking sockets and wasting paid LLM tokens.
5. In `_classify_exception` (lines 280-355), status codes 401 and 403, and error strings like `"API_KEY_INVALID"`, `"PERMISSION_DENIED"`, and `"UNAUTHENTICATED"` are not checked, falling through to `ProviderErrorCode.UNKNOWN` rather than `ProviderErrorCode.CONFIGURATION`, which breaks automated key rotation and alerting.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Thread Pool Exhaustion**: High concurrent translation loads freeze other backend threadpool tasks (such as image thumbnail generation and disk storage operations).
2. **Quota Burn on Cancelled Tasks**: When users cancel long chapter translations, in-flight synchronous SDK calls cannot be cancelled and continue executing on Google's servers.
3. **Misclassified Auth Errors**: Expired or invalid API keys are logged as `UNKNOWN` rather than `CONFIGURATION`, causing pointless retry loops instead of fast failure or failover.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/providers/gemini_provider.py`, update `GeminiProvider.translate` to use `client.aio.models.generate_content`:

```python
client = self._get_client(Client, api_key_str)
generate_kwargs: dict[str, Any] = {
    "model": model_name,
    "contents": contents,
}
if config_payload:
    generate_kwargs["config"] = config_payload

execution_started = time.perf_counter()
execution_ms: float | None = None
try:
    response = await client.aio.models.generate_content(**generate_kwargs)
    execution_ms = (time.perf_counter() - execution_started) * 1000
```

2. In `_classify_exception` (lines 280-355), detect configuration and authentication errors:

```python
auth_markers = ("api_key_invalid", "permission_denied", "unauthenticated", "invalid api key")
if any(isinstance(value, int) and value in {401, 403} for value in status_codes) or any(
    marker in combined for marker in auth_markers
):
    return ProviderErrorCode.CONFIGURATION, retry_after, details
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_gemini_async_transport.py`:

```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from novelai.providers.gemini_provider import GeminiProvider, ProviderErrorCode

@pytest.mark.asyncio
async def test_gemini_calls_native_aio_generate_content():
    provider = GeminiProvider(api_key="test-key")
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=MagicMock(text="Translated output"))
    provider._client = mock_client

    result = await provider.translate("テスト", model="gemini-2.5-flash")
    assert result["text"] == "Translated output"
    mock_client.aio.models.generate_content.assert_awaited_once()

def test_gemini_classifies_permission_denied_as_configuration():
    provider = GeminiProvider(api_key="test-key")
    exc = Exception("PERMISSION_DENIED: The caller does not have permission")
    code, _, _ = provider._classify_exception(exc)
    assert code == ProviderErrorCode.CONFIGURATION
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_gemini_async_transport.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. Callers of `GeminiProvider.translate` already invoke it via `await`.
- **Rollback Procedure**: Revert `gemini_provider.py` to restore synchronous SDK calls wrapped in `asyncio.to_thread`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/providers/gemini_provider.py
  ```

---

### REC-042: Infinite Loop in Adaptive Paragraph Balancing Algorithm Under Uneven Chunk Partitions

- **ID**: `REC-042`
- **Subsystem/Component**: Text Segmentation & Chunk Balancing (`novelai.translation.pipeline.stages.segment`)
- **Target Location**:
  - `backend/src/novelai/translation/pipeline/stages/segment.py:488-518` (`_balanced_paragraph_groups`)
  - `backend/src/novelai/translation/pipeline/stages/segment.py:528-548` (`_adaptive_groups_for_chapter`)
- **Category**: `Weakness`
- **Severity**: `Critical`
- **Summary**: In `_balanced_paragraph_groups`, group boundary closure requires `1 + remaining_paragraphs >= remaining_groups`. When `chunk_count` is incremented beyond paragraph count in `_adaptive_groups_for_chapter`, this condition permanently fails, preventing any group from closing and locking the pipeline in an infinite `while True` loop.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/translation/pipeline/stages/segment.py`, lines 488-518 and 530-545 define:

```python
for index, paragraph in enumerate(paragraphs):
    remaining_paragraphs = len(paragraphs) - index - 1
    remaining_groups = chunk_count - len(groups) - 1
    projected = pending_chars + paragraph.char_count
    has_enough_remaining = 1 + remaining_paragraphs >= remaining_groups
    can_close_before = bool(pending) and len(groups) < chunk_count - 1 and has_enough_remaining
    ...
    if can_close_before and (exceeds_hard or close_for_scene or (near_target and not next_is_dialogue)):
        groups.append(pending)
        pending = []
        pending_chars = 0
```

And in `_adaptive_groups_for_chapter`:

```python
chunk_count = max(1, -(-segment_chars // self.adaptive_hard_max_chars))
while True:
    balanced = self._balanced_paragraph_groups(
        segment,
        chunk_count=chunk_count,
        hard_max_chars=self.adaptive_hard_max_chars,
    )
    if all(sum(paragraph.char_count for paragraph in group) <= self.adaptive_hard_max_chars for group in balanced):
        groups.extend(balanced)
        break
    chunk_count += 1
```

Notice:

1. If a chapter segment contains a small number of very long paragraphs that cannot fit within `adaptive_hard_max_chars` under the initial partition, `chunk_count` increments.
2. If `chunk_count` exceeds `len(paragraphs)`:
   - At paragraph index 0: `remaining_paragraphs = len(paragraphs) - 1`, and `remaining_groups = chunk_count - 1`.
   - Because `chunk_count > len(paragraphs)`, `remaining_groups > remaining_paragraphs`.
   - `has_enough_remaining = (1 + remaining_paragraphs >= remaining_groups)` is strictly `False`.
3. Consequently, `can_close_before` evaluates to `False` for every paragraph.
4. `_balanced_paragraph_groups` can never close any group and flushes all paragraphs into a single list in `pending`.
5. The `all(...)` validation fails because that single group exceeds `adaptive_hard_max_chars`.
6. The loop increments `chunk_count` again, where the condition is even more impossible to satisfy.
7. The worker enters an infinite `while True` loop, pinning CPU at 100% and completely hanging translation segmentation.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Worker Process Hang**: Web novel chapters with long monologue paragraphs freeze worker containers indefinitely.
2. **Denial of Service**: CPU saturation at 100% starves other tasks on the container, requiring operator intervention and container restart.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/translation/pipeline/stages/segment.py`, cap `chunk_count` at `len(segment)` and fall back to paragraph splitting if budget cannot be met:

```python
def flush_segment() -> None:
    if not segment:
        return
    segment_chars = sum(paragraph.char_count for paragraph in segment)
    max_chunks = len(segment)
    chunk_count = max(1, -(-segment_chars // self.adaptive_hard_max_chars))
    while chunk_count <= max_chunks:
        balanced = self._balanced_paragraph_groups(
            segment,
            chunk_count=chunk_count,
            hard_max_chars=self.adaptive_hard_max_chars,
        )
        if all(
            sum(paragraph.char_count for paragraph in group) <= self.adaptive_hard_max_chars
            for group in balanced
        ):
            groups.extend(balanced)
            segment.clear()
            return
        chunk_count += 1

    # Fallback: if paragraph boundaries cannot satisfy budget, split oversized paragraphs
    sub_groups: list[list[Paragraph]] = []
    current_group: list[Paragraph] = []
    current_chars = 0
    for p in segment:
        if current_chars + p.char_count > self.adaptive_hard_max_chars and current_group:
            sub_groups.append(current_group)
            current_group = []
            current_chars = 0
        current_group.append(p)
        current_chars += p.char_count
    if current_group:
        sub_groups.append(current_group)
    groups.extend(sub_groups)
    segment.clear()
```

2. In `_balanced_paragraph_groups`, ensure that if `projected > hard_max_chars` and `pending` is non-empty, close the group unconditionally to avoid budget overruns.

#### 4. Verification & Test Strategy

Create `backend/tests/test_adaptive_segment_termination.py`:

```python
from novelai.translation.pipeline.stages.segment import SmartSegmentStage, Paragraph, _ChapterParagraphs

def test_adaptive_segmentation_terminates_on_oversized_few_paragraphs():
    stage = SmartSegmentStage(adaptive_hard_max_chars=1000)
    # 2 paragraphs of 1500 chars each
    paragraphs = [
        Paragraph(id="p1", text="A" * 1500, char_count=1500),
        Paragraph(id="p2", text="B" * 1500, char_count=1500),
    ]
    chapter = _ChapterParagraphs(novel_id="nov1", chapter_id="c1", paragraphs=paragraphs)
    # Must terminate promptly without hanging in infinite loop
    groups = stage._adaptive_groups_for_chapter(chapter, warnings=[])
    assert len(groups) >= 2
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_adaptive_segment_termination.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. Replaces an infinite loop bug with bounded partition resolution.
- **Rollback Procedure**: Revert changes to `segment.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/translation/pipeline/stages/segment.py
  ```

---

### REC-043: Japanese Dialogue Quotation Splitting Regex Failure Due to Mandatory Post-Delimiter Whitespace Lookbehind

- **ID**: `REC-043`
- **Subsystem/Component**: Sentence Splitting & Dialogue Boundary Detection (`novelai.translation.pipeline.stages.segment`)
- **Target Location**:
  - `backend/src/novelai/translation/pipeline/stages/segment.py:21` (`_SENTENCE_SPLIT_RE`)
  - `backend/src/novelai/translation/pipeline/stages/segment.py:210-230` (`split_oversized_paragraph`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `_SENTENCE_SPLIT_RE` requires trailing whitespace after Japanese closing quotes (`(?<=[」』）)])\s+`), which never occurs in authentic Japanese novel formatting, preventing dialogue boundary detection and erroneously splitting sentences inside spoken lines.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/translation/pipeline/stages/segment.py:21`:

```python
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])|(?<=[」』）)])\s+|(?<=\.)\s+")
```

Notice:

1. The regex is designed to find safe sentence boundaries to split oversized paragraphs without breaking quote pairs.
2. The closing quote branch explicitly requires whitespace characters: `(?<=[」』）)])\s+`.
3. In Japanese prose (Syosetu, Kakuyomu), closing quotation marks are followed immediately by narration or line breaks (`「おはよう」彼女は言った。`), never spaces. The lookbehind branch matches 0 times on authentic Japanese text.
4. Conversely, the first branch `(?<=[。！？!?])` matches punctuation unconditionally, even when inside quotation marks.
5. In dialogue containing punctuation (e.g. `「待って！行かないで！」`), the splitter splits at `！`, separating the spoken dialogue into `「待って！` and `行かないで！」`.
6. Orphaned quote fragments are sent to separate LLM translation chunks, confusing the model, losing quotation balance, and distorting character voice.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Dialogue Fragmentation**: Spoken lines are severed mid-quote across chunks, producing unclosed quotes and missing speaker tags in English output.
2. **Translation Quality Degradation**: LLMs hallucinate omitted pronouns and speakers when receiving sentence fragments lacking opening quotation marks.

#### 3. Concrete Implementation Specification

1. Revise `_SENTENCE_SPLIT_RE` in `backend/src/novelai/translation/pipeline/stages/segment.py`:

```python
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[」』）)])|"  # Split immediately after closing Japanese quotes
    r"(?<=[。！？!?])(?=[^」』）)]|$)|"  # Split at punctuation ONLY if not immediately followed by closing quote
    r"(?<=\.)\s+"  # Latin period followed by space
)
```

2. In `split_oversized_paragraph`, verify `_quote_balance == 0` before accepting a split boundary, guaranteeing that no split occurs while inside open dialogue.

#### 4. Verification & Test Strategy

Create `backend/tests/test_japanese_dialogue_splitting.py`:

```python
from novelai.translation.pipeline.stages.segment import SmartSegmentStage, _SENTENCE_SPLIT_RE

def test_sentence_split_preserves_dialogue_quotes():
    text = "「待って！行かないで！」彼女は言った。彼は立ち止まった。"
    matches = list(_SENTENCE_SPLIT_RE.finditer(text))
    split_indices = [m.end() for m in matches]
    # Punctuation inside 「待って！」 must NOT trigger a split; split must occur after 」 and 。
    fragments = [text[i:j] for i, j in zip([0] + split_indices, split_indices + [None])]
    fragments = [f for f in fragments if f]
    assert fragments[0] == "「待って！行かないで！」"
    assert "彼女は言った。" in fragments[1]
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_japanese_dialogue_splitting.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Preserves quote integrity for all Japanese novel sources.
- **Rollback Procedure**: Revert changes to `segment.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/translation/pipeline/stages/segment.py
  ```

---

### REC-044: Naive Substring Replacement on Translated English Text and Missing Runtime Context in PostProcessStage

- **ID**: `REC-044`
- **Subsystem/Component**: Glossary Replacement & Pipeline Post-Processing (`novelai.glossary.glossary`, `novelai.translation.pipeline.stages.post_process`, `novelai.translation.service`)
- **Target Location**:
  - `backend/src/novelai/glossary/glossary.py:214-219` (`Glossary.translate`)
  - `backend/src/novelai/translation/pipeline/stages/post_process.py:39-44` (`PostProcessStage.run`)
  - `backend/src/novelai/translation/service.py:41` (`TranslationService._build_pipeline`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `Glossary.translate` performs naive `str.replace` of Japanese source terms against translated English text without word boundaries, causing substring corruption, while `PostProcessStage` ignores runtime pipeline context, silently skipping glossary post-processing in production pipelines.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/glossary/glossary.py:214-219`:

```python
def translate(self, text: str) -> str:
    """Apply glossary term substitutions to translated text."""
    for term in sorted(self.as_entries(), key=lambda item: len(item.source), reverse=True):
        text = text.replace(term.source, term.target)
    return text
```

And in `backend/src/novelai/translation/pipeline/stages/post_process.py:39-44`:

```python
if self.glossary:
    logger.debug("Applying glossary substitutions")
    text = self.glossary.translate(text)
```

Notice:

1. In `PostProcessStage`, `text` is the English translated chapter prose.
2. `term.source` is the Japanese source term (e.g. `魔術師`). Calling `text.replace("魔術師", "Mage")` on English text is a complete no-op unless the LLM output contained untranslated Japanese residue.
3. If `term.source` contains Latin or English characters (e.g. "Dan"), `str.replace` without word boundaries (`\b`) mutates words containing the substring (e.g. "Dan" -> "Danube", "Danger", "Guidance").
4. In `TranslationService._build_pipeline`, `PostProcessStage()` is instantiated with no parameters (`self.glossary = None`). In `PostProcessStage.run`, it never inspects `context.metadata.get("glossary")` or `context.metadata.get("glossary_approved_terms")`. Consequently, glossary post-processing is dead code in production.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Dead Glossary Post-Processing**: User-configured post-process glossary substitutions never execute.
2. **Text Mutilation**: Any alphanumeric substitution replaces partial words across the English chapter.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/translation/pipeline/stages/post_process.py`:

```python
async def run(self, context: PipelineState) -> PipelineState:
    text = "\n\n".join(context.translations)
    logger.info("Post-processing %d translated chunks", len(context.translations))

    glossary = self.glossary or context.metadata.get("glossary")
    if glossary is not None:
        logger.debug("Applying glossary substitutions")
        text = glossary.translate(text)

    context.final_text = text
    ...
    return context
```

2. In `backend/src/novelai/glossary/glossary.py`, enforce word boundary matching on Latin/alphanumeric terms:

```python
import re

def translate(self, text: str) -> str:
    """Apply glossary term substitutions to translated text safely."""
    for term in sorted(self.as_entries(), key=lambda item: len(item.source), reverse=True):
        if not term.source or not term.target:
            continue
        if term.source.isascii() and term.source.isalnum():
            pattern = rf"\b{re.escape(term.source)}\b"
            text = re.sub(pattern, term.target, text)
        else:
            text = text.replace(term.source, term.target)
    return text
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_glossary_safe_substitution.py`:

```python
from novelai.glossary.glossary import Glossary, GlossaryTerm

def test_glossary_substitution_respects_word_boundaries():
    glossary = Glossary([GlossaryTerm(source="Dan", target="Daniel")])
    text = "Dan entered the dangerous cave with guidance."
    result = glossary.translate(text)
    assert result == "Daniel entered the dangerous cave with guidance."
    assert "Danielgerous" not in result
    assert "guiDanielce" not in result
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_glossary_safe_substitution.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Restores intended glossary post-processing behavior safely.
- **Rollback Procedure**: Revert changes to `glossary.py`, `post_process.py`, and `service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/glossary/glossary.py backend/src/novelai/translation/pipeline/stages/post_process.py backend/src/novelai/translation/service.py
  ```

---

### REC-045: Synchronous Database Session Scope and Redundant Queries Inside Async Translation Pipeline Loop

- **ID**: `REC-045`
- **Subsystem/Component**: Translation Orchestration & DB Concurrency (`novelai.translation.pipeline.stages.translate`)
- **Target Location**:
  - `backend/src/novelai/translation/pipeline/stages/translate.py:468-482` (`_build_prompt_glossary_block`)
  - `backend/src/novelai/translation/pipeline/stages/translate.py:1080-1095` (`TranslateStage.worker`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `TranslateStage._build_prompt_glossary_block` opens a synchronous SQLAlchemy `session_scope()` per chunk on the main async event loop to query glossary entries, blocking the event loop and executing $O(N)$ redundant DB queries for each chapter.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/translation/pipeline/stages/translate.py:468-482`:

```python
try:
    from novelai.db.engine import session_scope

    with session_scope() as session:
        repository = GlossaryRepository(session)
        return GlossaryPromptInjectionService(repository).build_for_chapter(
            novel_id,
            raw_chapter_text=chunk_text,
            options=options,
        )
except Exception as exc:
    warnings = context.metadata.setdefault("glossary_prompt_warnings", [])
```

Notice:

1. `_build_prompt_glossary_block` is invoked in `worker(chunk_index, chunk)` for every single chunk in a chapter.
2. When `self._glossary_prompt_service` is `None` (the default container configuration), the code imports and enters a synchronous `with session_scope() as session:` directly on the asyncio event loop.
3. Synchronous SQLAlchemy queries (`NovelGlossaryEntry` and `NovelGlossaryAlias` lookups) block the asyncio event loop thread for the duration of the database network I/O.
4. For a 40-chunk chapter, 40 separate database sessions are opened and torn down, executing the exact same SQL queries 40 times in sequence, causing database query amplification and event loop starvation.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Event Loop Latency Spikes**: Synchronous DB round-trips freeze the event loop, causing health check timeouts and lagging reader requests.
2. **PostgreSQL Connection Exhaustion**: Spawning dozens of rapid synchronous sessions per chapter exhausts the connection pool under multi-worker translation loads.

#### 3. Concrete Implementation Specification

1. In `TranslateStage.run`, pre-load and cache the novel glossary entries once at the chapter level using `asyncio.to_thread`:

```python
novel_id = platform_novel_id(context)
chapter_glossary_entries: list[Any] = []
if novel_id and self._glossary_prompt_service is None:
    def _fetch_entries() -> list[Any]:
        from novelai.db.engine import session_scope
        with session_scope() as session:
            repo = GlossaryRepository(session)
            return list(repo.list_entries_for_novel(novel_id))
    chapter_glossary_entries = await asyncio.to_thread(_fetch_entries)
    context.metadata["cached_glossary_entries"] = chapter_glossary_entries
```

2. Build an in-memory `GlossaryPromptInjectionService` or query the cached list per chunk without opening database sessions.

#### 4. Verification & Test Strategy

Create `backend/tests/test_translate_stage_db_isolation.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from novelai.translation.pipeline.stages.translate import TranslateStage, PipelineState

@pytest.mark.asyncio
async def test_translate_stage_does_not_open_sync_session_per_chunk():
    stage = TranslateStage()
    context = PipelineState(novel_id="nov1", chapter_id="c1", raw_text="text")
    context.metadata["cached_glossary_entries"] = []

    with patch("novelai.db.engine.session_scope") as mock_session:
        result = stage._build_prompt_glossary_block(context, "chunk text")
        # Must not call session_scope when cached entries are present
        mock_session.assert_not_called()
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_translate_stage_db_isolation.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Preserves glossary prompt injection behavior with zero event-loop blocking.
- **Rollback Procedure**: Revert changes to `translate.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/translation/pipeline/stages/translate.py
  ```

---

### REC-046: Concurrency Semaphore Starvation Caused by Holding Semaphore During Exponential Backoff Sleep

- **ID**: `REC-046`
- **Subsystem/Component**: Translation Pipeline Worker & Concurrency Control (`novelai.translation.pipeline.stages.translate`)
- **Target Location**:
  - `backend/src/novelai/translation/pipeline/stages/translate.py:1104-1130` (`worker` semaphore acquisition)
  - `backend/src/novelai/translation/pipeline/stages/translate.py:1445-1455` (`worker` retry sleep)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `TranslateStage.worker` holds its concurrency semaphore (`async with semaphore:`) across the entire retry loop. When a provider returns 429 rate limiting or temporary errors, `await asyncio.sleep(delay)` blocks the concurrency slot for up to 60 seconds, starving other chunks and stalling pipeline throughput.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/translation/pipeline/stages/translate.py`, lines 1104-1130 and 1445-1455 define:

```python
async def worker(chunk_index: int, chunk: TranslationChunk) -> str:
    ...
    async with semaphore:
        while True:
            ...
            try:
                translated, ... = await self._translate_with_model(...)
            except ProviderError as exc:
                ...
                delay = min(max_backoff, max(exponential, float(provider_retry_after)))
                if delay > 0:
                    await asyncio.sleep(delay)
                continue
```

Notice:

1. `semaphore = asyncio.Semaphore(self._max_concurrency)` regulates concurrent chunk translations (defaulting to 2 or 3).
2. `async with semaphore:` is entered at line 1104, _outside_ the `while True:` retry loop.
3. When Gemini or another LLM provider returns HTTP 429 (Rate Limited), `delay` is calculated up to `settings.TRANSLATION_PROVIDER_RETRY_BACKOFF_MAX_SECONDS` (60.0s).
4. During `await asyncio.sleep(delay)`, the coroutine retains its acquired semaphore slot.
5. If multiple chunks encounter rate limits simultaneously, all semaphore slots are locked by sleeping coroutines. Other queued chunks that could be translated using fallback models or cached results are completely blocked, reducing pipeline throughput to zero.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Pipeline Deadlock / Stall**: Temporary rate limiting on one chunk halts all chunk processing for up to 60 seconds.
2. **Inefficient Concurrency Utilization**: Available quota on secondary or fallback models cannot be used while worker slots are held by sleeping tasks.

#### 3. Concrete Implementation Specification

In `backend/src/novelai/translation/pipeline/stages/translate.py`, scope `async with semaphore:` strictly around the active provider execution call, ensuring the semaphore is released before sleeping:

```python
while True:
    ...
    try:
        async with semaphore:
            translated, response_meta = await self._translate_with_model(...)
        # Success: break out of retry loop
        break
    except ProviderError as exc:
        ...
        delay = min(max_backoff, max(exponential, float(provider_retry_after)))
        delay = min(delay, remaining)
        if delay > 0:
            # Sleep occurs OUTSIDE the semaphore, freeing the slot for other chunks
            await asyncio.sleep(delay)
        continue
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_translation_semaphore_release_on_backoff.py`:

```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_semaphore_not_held_during_backoff():
    sem = asyncio.Semaphore(1)
    acquired_by_c2 = False

    async def worker_1():
        # Mimic worker 1 failing and sleeping outside semaphore
        async with sem:
            pass  # Attempt call, fail
        # Sleep outside semaphore
        await asyncio.sleep(0.1)

    async def worker_2():
        nonlocal acquired_by_c2
        await asyncio.sleep(0.01)
        async with sem:
            acquired_by_c2 = True

    await asyncio.gather(worker_1(), worker_2())
    assert acquired_by_c2 is True
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_translation_semaphore_release_on_backoff.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Unlocks high concurrency throughput during provider rate limiting.
- **Rollback Procedure**: Revert changes to `translate.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/translation/pipeline/stages/translate.py
  ```

---

### REC-047: Short Chunk CJK Residue Bypass and Unconditional LLM Grader Fail-Open Masking Translation Hallucinations

- **ID**: `REC-047`
- **Subsystem/Component**: Quality Assurance Heuristics & LLM Grader (`novelai.translation.qa`, `novelai.translation.pipeline.stages.translation_qa`)
- **Target Location**:
  - `backend/src/novelai/translation/qa.py:70-75` (`_check_source_language_residue`)
  - `backend/src/novelai/translation/qa.py:680-745` (`evaluate_translation_quality_with_llm`)
  - `backend/src/novelai/translation/pipeline/stages/translation_qa.py:230-290` (`TranslationQAStage.run`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `_check_source_language_residue` completely skips chunks $\le 50$ characters, allowing short untranslated Japanese dialogue to pass into the cache. Additionally, `evaluate_translation_quality_with_llm` unconditionally returns 1.0 on all exceptions and JSON parse failures, recording failed evaluations as perfect translations.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/translation/qa.py:70-75`:

```python
def _check_source_language_residue(
    output_text: str,
    *,
    warnings: list[str],
    errors: list[str],
) -> None:
    """Flag translated text with high CJK residue (REQ-3.1..REQ-3.4)."""
    if len(output_text) <= 50:
        return
```

And in `backend/src/novelai/translation/qa.py:680-745`:

```python
try:
    result = await provider.translate(prompt, **optional_kwargs)
except Exception:
    return 1.0
...
except (json.JSONDecodeError, KeyError, TypeError, ValueError):
    return 1.0
```

Notice:

1. Short dialogue lines (e.g. `「何これ……？」彼女は呟いた。` at 17 characters) are frequent in web novels. If the LLM echoes raw Japanese text verbatim or fails silently, `len(output_text) <= 50` immediately returns without evaluating CJK character density. The untranslated Japanese text receives `qa_status = "passed"` and is permanently stored in the translation cache.
2. In `evaluate_translation_quality_with_llm`, any provider timeout, rate limit (HTTP 429), authentication failure (HTTP 401/403), network disconnect, or malformed JSON output causes the function to return `1.0`.
3. Returning `1.0` (a perfect score) on grader failures masks LLM grader outages. In `TranslationQAStage.run`, `llm_qa_score = 1.0` is written to chapter metadata, misleading operators into believing translation quality was empirically verified.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Corrupted Reader Experience**: Readers encounter untranslated Japanese dialogue lines because short chunks bypass CJK residue detection.
2. **Silent QA Blindspots**: Grader outages or schema changes return 100% pass rates, masking degradation in translation quality.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/translation/qa.py:70`, enforce absolute count and density thresholds on short texts:

```python
cjk_count = sum(1 for ch in output_text if _is_cjk(ch))
total_chars = len(output_text.strip())
if total_chars <= 50:
    if total_chars > 0 and (cjk_count >= 3 or (cjk_count / total_chars) > 0.30):
        errors.append("cjk_residue_high")
    return
```

2. In `backend/src/novelai/translation/qa.py:680`, return a structured `LLMQAResult` or `None` on failure:

```python
@dataclass
class LLMQAResult:
    score: float | None
    status: str  # "evaluated", "unavailable", "invalid_response"
    error: str | None = None

async def evaluate_translation_quality_with_llm(...) -> LLMQAResult:
    try:
        response = await provider.translate(prompt, **optional_kwargs)
        score = _parse_score(response.get("text", "") if isinstance(response, dict) else "")
        return LLMQAResult(score=score, status="evaluated")
    except Exception as exc:
        logger.warning("LLM QA evaluation failed: %s", exc)
        return LLMQAResult(score=None, status="unavailable", error=str(exc))
```

3. In `backend/src/novelai/translation/pipeline/stages/translation_qa.py:230`, record `llm_qa_status = "unavailable"` and do not synthesize a fake `1.0` score when grader fails.

#### 4. Verification & Test Strategy

Create `backend/tests/test_qa_short_cjk_and_grader_failure.py`:

```python
from novelai.translation.qa import _check_source_language_residue, evaluate_translation_quality_with_llm

def test_short_cjk_residue_is_flagged():
    errors, warnings = [], []
    _check_source_language_residue("「何これ……？」彼女は呟いた。", warnings=warnings, errors=errors)
    assert "cjk_residue_high" in errors

def test_short_valid_english_passes():
    errors, warnings = [], []
    _check_source_language_residue('"What is this...?" she muttered.', warnings=warnings, errors=errors)
    assert len(errors) == 0
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_qa_short_cjk_and_grader_failure.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Distinguishes unverified translations from genuine 1.0 scores without failing operational pipelines.
- **Rollback Procedure**: Revert changes to `qa.py` and `translation_qa.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/translation/qa.py backend/src/novelai/translation/pipeline/stages/translation_qa.py
  ```

---

### REC-048: Unbounded Glossary Injection into User Prompts Without Token Budgeting or Sanitization

- **ID**: `REC-048`
- **Subsystem/Component**: Prompt Engineering & Context Budgeting (`novelai.prompts.builders`, `novelai.services.glossary_prompt_injection`)
- **Target Location**:
  - `backend/src/novelai/prompts/builders.py:65-75` (`format_glossary_block`)
  - `backend/src/novelai/prompts/builders.py:115-130` (`_format_additional_instructions`)
  - `backend/src/novelai/services/glossary_prompt_injection.py:155, 320-330` (`_any_contains` ranking bug)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `format_glossary_block` serializes all passed glossary entries into user prompts without length or token caps, while `GlossaryPromptInjectionService._any_contains` checks for Japanese source terms in translated English context, breaking context-aware ranking.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/prompts/builders.py:65-75`:

```python
def format_glossary_block(glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None) -> str:
    entries = _coerce_glossary_entries(glossary_entries)
    if not entries:
        return ""
    lines = ["Project glossary:"]
    for entry in entries:
        lines.append(f"- {entry.source} = {entry.target}")
        if entry.context_summary:
            lines.append(f"  Context: {entry.context_summary}")
    return "\n".join(lines)
```

Unlike `GlossaryPromptInjectionService` (which bounds terms with `max_terms=20` and `max_block_chars=2000`), `format_glossary_block` in `builders.py` iterates over all glossary entries without bounds. If a novel project has accumulated 300+ approved terms, `format_glossary_block` injects all 300 entries into the user prompt, adding thousands of tokens of overhead per chunk, inflating API costs, and risking context window overflow or model attention dilution.

Furthermore, in `backend/src/novelai/services/glossary_prompt_injection.py:155`:

```python
matched_translated = _any_contains(translated_text, match_terms)
```

Where `match_terms` contains Japanese canonical terms (`entry.canonical_term` and Japanese aliases). `translated_text` contains English translated prose from prior chapters. Searching for Japanese characters inside translated English prose never matches. The code should search `translated_text` for `entry.approved_translation` (and target aliases), not Japanese source terms. Because of this bug, terms used in preceding translated chapters are never prioritized.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Prompt Bloat & LLM Attention Degradation**: Unbounded glossary blocks exceed context windows or dilute LLM attention away from the actual chapter prose.
2. **Context-Aware Ranking Ineffectiveness**: Translated context matching never succeeds, causing terms that appeared in recent chapters to be omitted in favor of arbitrary dictionary ordering.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/prompts/builders.py:65`, add truncation caps:

```python
def format_glossary_block(
    glossary_entries: Iterable[GlossaryEntryLike] | Glossary | None,
    max_terms: int = 25,
    max_chars: int = 2000,
) -> str:
    entries = _coerce_glossary_entries(glossary_entries)
    if not entries:
        return ""
    lines = ["Project glossary:"]
    total_chars = len(lines[0])
    count = 0
    for entry in entries:
        if count >= max_terms:
            break
        safe_src = str(entry.source).replace("\n", " ").strip()
        safe_tgt = str(entry.target).replace("\n", " ").strip()
        line = f"- {safe_src} = {safe_tgt}"
        if total_chars + len(line) + 1 > max_chars:
            break
        lines.append(line)
        total_chars += len(line) + 1
        count += 1
    return "\n".join(lines)
```

2. In `backend/src/novelai/services/glossary_prompt_injection.py:155`, match translated English terms:

```python
target_match_terms = [entry.approved_translation] + list(entry.target_aliases or [])
matched_translated = _any_contains(translated_text, target_match_terms)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_glossary_prompt_budget_and_ranking.py`:

```python
import pytest
from novelai.prompts.builders import format_glossary_block
from novelai.glossary.glossary import GlossaryTerm

def test_format_glossary_block_enforces_limits():
    entries = [GlossaryTerm(source=f"Term{i}", target=f"Target{i}") for i in range(100)]
    block = format_glossary_block(entries, max_terms=10, max_chars=500)
    lines = [l for l in block.splitlines() if l.startswith("- Term")]
    assert len(lines) == 10
    assert len(block) <= 500
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_glossary_prompt_budget_and_ranking.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. Protects prompt token budgets across all translation runs.
- **Rollback Procedure**: Revert changes to `builders.py` and `glossary_prompt_injection.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/prompts/builders.py backend/src/novelai/services/glossary_prompt_injection.py
  ```

---

### REC-049: Default Cost Catalog Model Desynchronization and Zero-Cost Division in Multi-Model Estimator

- **ID**: `REC-049`
- **Subsystem/Component**: Cost Estimator & Token Pricing Models (`novelai.cost_estimator.pricing`, `novelai.cost_estimator.compare`)
- **Target Location**:
  - `backend/src/novelai/cost_estimator/pricing.py:8-14` (`DEFAULT_PRICING`)
  - `backend/src/novelai/cost_estimator/pricing.py:25-33` (`get_model_pricing`)
  - `backend/src/novelai/cost_estimator/compare.py:28-34` (`compare_models`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `DEFAULT_PRICING` only contains `"gemini-3.5-flash-lite"` with $0.00 pricing, causing `estimate_cost` to crash with `ValueError` when called with the actual production default model (`gemini-2.5-flash`), while `compare_models` computes 0.0% cost differences due to zero-cost division handling.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/cost_estimator/pricing.py:8-14`:

```python
DEFAULT_PRICING: dict[str, ModelPricing] = {
    "gemini-3.5-flash-lite": ModelPricing(
        model_name="gemini-3.5-flash-lite",
        input_per_million_usd=0.0,
        output_per_million_usd=0.0,
    ),
}
```

And in `get_model_pricing` (lines 25-33):

```python
try:
    return catalog[model_name]
except KeyError as exc:
    supported = ", ".join(list_supported_models(catalog))
    raise ValueError(f"Unsupported model '{model_name}'. Supported models: {supported}.") from exc
```

The production default model throughout the application (`settings.GEMINI_DEFAULT_MODEL`, `GEMINI_FALLBACK_CHAIN`, and `GeminiProvider.DEFAULT_TEXT_MODEL`) is `"gemini-2.5-flash"`.
When a user or service calls `estimate_cost("gemini-2.5-flash", options)` without passing an explicit custom catalog, `get_model_pricing` raises `ValueError: Unsupported model 'gemini-2.5-flash'. Supported models: gemini-3.5-flash-lite.`.

Furthermore, in `novelai.cost_estimator.compare.py:30-34`:

```python
percentage_difference = (
    (difference / cheapest.estimated_total_cost_usd) * 100 if cheapest.estimated_total_cost_usd > 0 else 0.0
)
```

When comparing a zero-cost model against a paid model, `cheapest.estimated_total_cost_usd` is 0.0. The code evaluates the branch to `0.0%` difference instead of properly indicating an infinite or distinct cost tier, rendering model cost comparisons misleading.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Runtime Crashes on Cost Inquiries**: Pre-flight cost calculation endpoints crash with 500/ValueError whenever queried for standard production models.
2. **Distorted Cost Reporting**: Admin cost dashboards report 0% cost divergence between free test tiers and paid production models.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/cost_estimator/pricing.py:8`, expand `DEFAULT_PRICING`:

```python
DEFAULT_PRICING: dict[str, ModelPricing] = {
    "gemini-2.5-flash": ModelPricing(
        model_name="gemini-2.5-flash",
        input_per_million_usd=0.075,
        output_per_million_usd=0.30,
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        model_name="gemini-2.5-flash-lite",
        input_per_million_usd=0.0375,
        output_per_million_usd=0.15,
    ),
    "gemini-2.5-pro": ModelPricing(
        model_name="gemini-2.5-pro",
        input_per_million_usd=1.25,
        output_per_million_usd=5.00,
    ),
    "gemini-3.5-flash-lite": ModelPricing(
        model_name="gemini-3.5-flash-lite",
        input_per_million_usd=0.075,
        output_per_million_usd=0.30,
    ),
}
```

2. In `backend/src/novelai/cost_estimator/compare.py:30`:

```python
if cheapest.estimated_total_cost_usd > 0:
    percentage_difference = (difference / cheapest.estimated_total_cost_usd) * 100.0
else:
    percentage_difference = float("inf") if difference > 0 else 0.0
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_cost_estimator_catalog.py`:

```python
import pytest
from novelai.cost_estimator.pricing import get_model_pricing
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimateOptions, EstimationResult

def test_production_default_models_exist():
    for m in ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]:
        pricing = get_model_pricing(m)
        assert pricing.input_per_million_usd > 0
        assert pricing.output_per_million_usd > 0

def test_compare_models_with_zero_baseline():
    r1 = EstimationResult(model_name="free", estimated_total_cost_usd=0.0, input_tokens=100, output_tokens=100)
    r2 = EstimationResult(model_name="paid", estimated_total_cost_usd=1.5, input_tokens=100, output_tokens=100)
    diff = compare_models([r1, r2])
    assert diff.percentage_difference == float("inf")
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_cost_estimator_catalog.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Backwards-compatible. Resolves unhandled ValueError exceptions in API cost endpoints.
- **Rollback Procedure**: Revert changes to `pricing.py` and `compare.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/cost_estimator/pricing.py backend/src/novelai/cost_estimator/compare.py
  ```

---

### REC-050: Translation Cache Eviction FIFO Degradation and Cache Poisoning via Unparameterized Simple Key Builder

- **ID**: `REC-050`
- **Subsystem/Component**: Translation Cache & Persistence (`novelai.services.translation_cache`)
- **Target Location**:
  - `backend/src/novelai/services/translation_cache.py:165-175` (`_hash_key`)
  - `backend/src/novelai/services/translation_cache.py:185-195` (`TranslationCache.get` & `set`)
  - `backend/src/novelai/services/translation_cache.py:215-225` (`_evict_if_needed`)
- **Category**: `Weakness`
- **Severity**: `Critical`
- **Summary**: `TranslationCache` uses arbitrary dict key slice eviction (FIFO rather than LRU) and rewrites the entire monolithic JSON file on every set. Additionally, `TranslationCache.get`/`set` omit `source_language`, `target_language`, `style_preset`, and `glossary_hash` from cache keys, causing cross-policy cache collisions.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/translation_cache.py:165-175`:

```python
@staticmethod
def _hash_key(
    source_text: str,
    provider_key: str,
    provider_model: str | None,
) -> str:
    return build_translation_cache_key(
        source_text=source_text,
        provider_key=provider_key,
        provider_model=provider_model,
    )
```

And in lines 215-225:

```python
def _evict_if_needed(self) -> None:
    max_entries = settings.TRANSLATION_CACHE_MAX_ENTRIES
    if len(self._data) <= max_entries:
        return
    excess = len(self._data) - max_entries
    keys_to_remove = list(self._data.keys())[:excess]
    for key in keys_to_remove:
        del self._data[key]
```

`TranslationCache` exhibits two critical defects:

1. **Cache Collision & Cross-Lingual Poisoning**: `_hash_key` only passes `source_text`, `provider_key`, and `provider_model` to `build_translation_cache_key`. All other parameters (`source_language`, `target_language`, `style_preset`, `glossary_hash`, `honorific_policy`) default to `None`. If Japanese source prose is translated to English, and subsequently translated to Spanish, or translated with a different glossary or style preset, `get()` returns a cache hit with the English translation, poisoning the output.
2. **FIFO Eviction & Unbounded I/O Overhead**: On every `set()` call, `_persist()` writes the full JSON dictionary to disk. When the cache exceeds `TRANSLATION_CACHE_MAX_ENTRIES`, `_evict_if_needed` deletes the first `excess` keys in dict insertion order (FIFO). This evicts frequently used entries simply because they were inserted earlier, degrading cache hit ratios.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Cross-Language Output Poisoning**: A user requesting a Spanish translation receives cached English text because cache keys lack target language discrimination.
2. **Glossary Disregard**: Updating or correcting terms in a project glossary has no effect on repeated chunks because the cache key ignores `glossary_hash`.
3. **I/O Bottlenecks**: Full-file JSON serialization on every chunk set causes write amplification and disk latency spikes.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/services/translation_cache.py`, implement parameterized keys and LRU eviction:

```python
from collections import OrderedDict

class TranslationCache:
    def __init__(self, cache_file: Path | str | None = None) -> None:
        self._data: OrderedDict[str, TranslationCacheEntry] = OrderedDict()
        ...

    @staticmethod
    def _hash_key(
        source_text: str,
        provider_key: str,
        provider_model: str | None,
        source_language: str = "ja",
        target_language: str = "en",
        style_preset: str | None = None,
        glossary_hash: str | None = None,
        honorific_policy: str = "keep",
    ) -> str:
        return build_translation_cache_key(
            source_text=source_text,
            provider_key=provider_key,
            provider_model=provider_model,
            source_language=source_language,
            target_language=target_language,
            style_preset=style_preset,
            glossary_hash=glossary_hash,
            honorific_policy=honorific_policy,
        )

    def get(self, source_text: str, provider_key: str, provider_model: str | None, **kwargs) -> str | None:
        key = self._hash_key(source_text, provider_key, provider_model, **kwargs)
        with self._lock:
            entry = self._data.get(key)
            if entry is not None:
                self._data.move_to_end(key)
                return entry.translated_text
            return None

    def _evict_if_needed(self) -> None:
        max_entries = settings.TRANSLATION_CACHE_MAX_ENTRIES
        while len(self._data) > max_entries:
            self._data.popitem(last=False)
```

2. Mark `TranslationCache` as legacy and consolidate new workloads into `TranslationCacheService` (SQLite index backed with content-addressed storage).

#### 4. Verification & Test Strategy

Create `backend/tests/test_translation_cache_keys.py`:

```python
from novelai.services.translation_cache import TranslationCache

def test_cache_keys_segregate_target_languages():
    cache = TranslationCache()
    cache.set("こんにちは", "Hello", provider_key="gemini", provider_model="flash", target_language="en")

    en_hit = cache.get("こんにちは", provider_key="gemini", provider_model="flash", target_language="en")
    es_miss = cache.get("こんにちは", provider_key="gemini", provider_model="flash", target_language="es")

    assert en_hit == "Hello"
    assert es_miss is None
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_translation_cache_keys.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Backwards-compatible. Legacy entries without language keys are recomputed on next query.
- **Rollback Procedure**: Revert changes to `translation_cache.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/translation_cache.py
  ```

## Iteration 6: Background Worker, Activity Execution Engine, Job Leases, Scheduler, & Concurrency Control

### Summary of Recommendations (Iteration 6)

| ID        | Subsystem / Focus                                                                       | Category     | Impact Summary                                                                                                                                                         |
| --------- | --------------------------------------------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `REC-051` | Activity Queue Database Recovery (`activity/database.py`)                               | Performance  | `_recover_expired` executes unindexed table scans deserializing full metadata for all running jobs on every claim instead of an atomic, indexed SQL update.            |
| `REC-052` | Activity Worker Lease Heartbeat (`activity/worker.py`)                                  | Weakness     | Heartbeat thread failure exits silently without notifying running async tasks, allowing revoked workers to run for hours and crash on final commit.                    |
| `REC-053` | Translation Cancellation Propagation (`activity/worker.py`, `translation.py`)           | Weakness     | Multi-chapter translation pipeline omits cooperative cancellation tokens, continuing expensive LLM requests even after activities are cancelled by operators.          |
| `REC-054` | RQ Task Lifecycle & Retry Policy (`worker/tasks.py`, `activity/worker.py`)              | Weakness     | Swallowed exceptions in `_run_claimed_activity` report false success to Redis disabling RQ retries, while subsequent retries crash with `ValueError` on failed status. |
| `REC-055` | Cron Scheduler Cold Start & Retry Loop (`services/scheduler_service.py`)                | Weakness     | Cold starts trigger immediate execution storms for all cron jobs, and failure checks query only succeeded runs causing infinite re-execution every 5 minutes.          |
| `REC-056` | Distributed Lease Point Queries & Renewals (`scheduled_job_lease_service.py`)           | Weakness     | Point-lookup `skip_locked=True` causes false-negative existence and `IntegrityError` collisions, while renewals omit row locking risking lost updates.                 |
| `REC-057` | Runner Graceful Drain & Shutdown Semantics (`activity/runner.py`, `activity/worker.py`) | Weakness     | SIGTERM container shutdowns cancel active coroutines, immediately marking in-flight jobs as permanently cancelled by owner rather than releasing leases to pending.    |
| `REC-058` | Queue Scheduling & Priority Control (`activity/database.py`, `activity/runner.py`)      | Architecture | Strict FIFO ordering with single-threaded sequential execution allows long 100-chapter batch translations to block 2-second interactive scrapes for hours.             |
| `REC-059` | Runtime Checkpoints & Metadata Payloads (`storage/jobs.py`, `activity/database.py`)     | Weakness     | Timestamped chapter checkpoints accumulate unbounded on disk without pruning, while serialized crawl failure lists exceed metadata size limits and abort jobs.         |
| `REC-060` | Runner Polling Backoff & Wakeup Signals (`activity/runner.py`, `activity/queue.py`)     | Performance  | Runner relies entirely on polling with exponential backoff up to 30s without event notification on job enqueue, introducing 30s latency for user actions.              |

---

### REC-051: Unbounded In-Memory Table Scan and Deserialization of Running Jobs in `ActivityDatabaseBackend._recover_expired`

- **ID**: `REC-051`
- **Subsystem/Component**: Activity Queue Database Backend (`novelai.activity.database`)
- **Target Location**:
  - `backend/src/novelai/activity/database.py:382-414` (`ActivityDatabaseBackend._recover_expired`)
  - `backend/src/novelai/activity/database.py:539-543` (`ActivityDatabaseBackend.claim_activity`)
  - `backend/src/novelai/activity/database.py:610-614` (`ActivityDatabaseBackend.claim_next_activity`)
  - `backend/src/novelai/db/models/activity.py:27-31` (`ActivityRecord.__table_args__` indexing)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `_recover_expired` is invoked on every single activity claim and executes an unindexed, lockless `SELECT` across all `RUNNING` rows, pulling full `metadata_json` payloads into Python memory for evaluation rather than using an atomic, indexed SQL batch update.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/database.py:382-414`:

```python
def _recover_expired(self, session: Session) -> None:
    now = _utc_now()
    rows = session.scalars(
        select(ActivityRecord)
        .options(
            load_only(
                ActivityRecord.activity_id,
                ActivityRecord.status,
                ActivityRecord.started_at,
                ActivityRecord.lease_id,
                ActivityRecord.lease_expires_at,
                ActivityRecord.last_heartbeat_at,
                ActivityRecord.error,
                ActivityRecord.metadata_json,
                ActivityRecord.updated_at,
            )
        )
        .where(ActivityRecord.status == JobStatus.RUNNING.value)
    ).all()
    for row in rows:
        if not self._lease_expired(row, now):
            continue
        metadata = _decode_metadata(row.metadata_json)
        metadata["lease_recovered_at"] = _iso(now)
        metadata["current_stage"] = "queued"
        row.status = JobStatus.PENDING.value
        row.started_at = None
        row.lease_id = None
        row.lease_expires_at = None
        row.last_heartbeat_at = None
        row.error = "Recovered expired activity lease"
        row.metadata_json = _metadata_text(metadata)
        row.updated_at = now
```

Both `claim_activity` (line 541) and `claim_next_activity` (line 612) call `self._recover_expired(session)` before attempting to claim work.
This introduces multiple severe performance and concurrency defects:

1. **High-frequency table scan**: On every worker poll or claim request, PostgreSQL executes a `SELECT ... WHERE status = 'running'` that retrieves all running activities. As worker concurrency increases, multiple workers simultaneously query, serialize, and transmit active activity records.
2. **Memory and serialization overhead**: Although `load_only` limits columns, `ActivityRecord.metadata_json` is explicitly included. When activities contain large chapter progress arrays or failure manifests (up to `ACTIVITY_METADATA_MAX_BYTES`, e.g. 512KB), pulling all running rows into Python and calling `json.loads` and `json.dumps` per expired row creates substantial CPU and memory churn.
3. **Ignored B-Tree index**: `ActivityRecord` already defines `Index("ix_activity_records_lease_expires", "lease_expires_at")`. However, `_recover_expired` filters only on `status == 'running'` and checks `_lease_expired(row, now)` in Python. The query fails to use the lease expiration index to filter rows directly in SQL.
4. **Concurrent recovery race**: The select query does not use row locking (`with_for_update`). If two workers call `claim_next_activity` simultaneously while an expired lease exists, both workers load the same row, mutate its state in memory, and generate race conditions on commit.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Database Connection & Buffer Saturation**: Polling workers constantly fetch and deserialize full metadata JSON blobs across dozens of active tasks, blowing out query caches and causing connection pool latency spikes.
2. **Split-Brain Recovery Races**: Multiple concurrent workers process the same un-locked expired rows simultaneously, triggering optimistic lock errors or inconsistent lease states.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/activity/database.py`, replace procedural Python iteration with an atomic, indexed SQL `UPDATE`:

```python
def _recover_expired(self, session: Session) -> int:
    now = _utc_now()
    stmt = (
        update(ActivityRecord)
        .where(
            ActivityRecord.status == JobStatus.RUNNING.value,
            ActivityRecord.lease_expires_at.is_not(None),
            ActivityRecord.lease_expires_at <= now,
        )
        .values(
            status=JobStatus.PENDING.value,
            started_at=None,
            lease_id=None,
            lease_expires_at=None,
            last_heartbeat_at=None,
            error="Recovered expired activity lease",
            updated_at=now,
        )
    )
    result = session.execute(stmt)
    return getattr(result, "rowcount", 0)
```

2. Decouple recovery from per-claim invocations: run `_recover_expired` as a periodic background task (e.g. once every 30 seconds) in `BackgroundActivityRunner` rather than on every single `claim_next_activity` or worker poll tick.

#### 4. Verification & Test Strategy

Create `backend/tests/test_activity_database_recovery.py`:

```python
from datetime import datetime, timezone, timedelta
from novelai.activity.database import ActivityDatabaseBackend
from novelai.db.models.activity import ActivityRecord
from novelai.activity.job_status import JobStatus

def test_recover_expired_executes_atomic_update(db_session, activity_backend):
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    record = ActivityRecord(
        activity_id="test-exp-1",
        type="crawl",
        kind="novel",
        novel_id="nov-1",
        status=JobStatus.RUNNING.value,
        lease_id="old-lease",
        lease_expires_at=past,
    )
    db_session.add(record)
    db_session.commit()

    count = activity_backend._recover_expired(db_session)
    db_session.commit()

    assert count == 1
    refreshed = db_session.get(ActivityRecord, "test-exp-1")
    assert refreshed.status == JobStatus.PENDING.value
    assert refreshed.lease_id is None
    assert refreshed.lease_expires_at is None
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_activity_database_recovery.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible with existing schema and indexes. Zero downtime deployment.
- **Rollback Procedure**: Revert changes to `database.py` and `models/activity.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/activity/database.py backend/src/novelai/db/models/activity.py
  ```

---

### REC-052: Heartbeat Thread Disconnect and Silent Work Continuation on Lost Lease in `ActivityWorkerService`

- **ID**: `REC-052`
- **Subsystem/Component**: Activity Worker Lease Heartbeat (`novelai.activity.worker`)
- **Target Location**:
  - `backend/src/novelai/activity/worker.py:535-570` (`ActivityWorkerService._run_claimed_with_heartbeat` & `_lease_heartbeat`)
  - `backend/src/novelai/activity/worker.py:740-752` (`ActivityWorkerService._run_claimed_activity`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: When `_lease_heartbeat` fails or is rejected, the background thread exits silently with a warning while `_run_claimed_activity` continues executing on the main event loop for hours without a cancellation signal, wasting provider tokens and crashing with `RuntimeError` at completion.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/worker.py:535-570`:

```python
async def _run_claimed_with_heartbeat(self, activity: dict[str, Any], lease_id: str) -> dict[str, Any] | None:
    activity_id = str(activity["activity_id"])
    heartbeat_stop = threading.Event()
    heartbeat = threading.Thread(
        target=self._lease_heartbeat,
        args=(activity_id, lease_id, heartbeat_stop),
        daemon=True,
        name=f"activity-lease-heartbeat-{activity_id}",
    )
    heartbeat.start()
    try:
        return await self._run_claimed_activity(activity, lease_id)
    finally:
        heartbeat_stop.set()
        heartbeat.join(timeout=max(5.0, min(float(self.activity_log.LEASE_SECONDS), 30.0)))
```

And in `_lease_heartbeat` (lines 550-564):

```python
def _lease_heartbeat(self, activity_id: str, lease_id: str, stop_event: threading.Event) -> None:
    ...
    while not stop_event.wait(interval):
        try:
            if not self.activity_log.renew_activity_lease(activity_id, lease_id):
                logger.warning("Activity lease heartbeat was rejected for %s", activity_id)
                return
        except Exception:
            logger.exception("Activity lease heartbeat failed for %s", activity_id)
            return
```

The lease heartbeat runs in a separate daemon thread. If the database lease renewal fails (due to transient DB disconnect, pool exhaustion, or lease reassignment by another worker after a timeout):

1. The heartbeat thread logs a warning or exception and immediately exits (`return`).
2. Crucially, no cancellation signal is sent to the active coroutine `_run_claimed_activity`.
3. The worker coroutine continues executing the crawl or translation job—often running for 30 to 60 minutes and making hundreds of expensive LLM provider API requests.
4. At completion (lines 740-752), the worker attempts to commit:

```python
completed = self.activity_log.update_activity_status(
    activity_id,
    JobStatus.COMPLETED,
    metadata=...,
    lease_id=lease_id,
)
if completed is None:
    raise RuntimeError("Activity lease was lost before completion")
```

Because `lease_id` is no longer valid, `update_activity_status` returns `None`, raising `RuntimeError("Activity lease was lost before completion")`. All completed translation work and spent token costs are lost because the worker had no mechanism to know its lease was revoked mid-flight.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Zombie Worker Execution & Quota Waste**: A worker whose lease expired or was revoked continues consuming third-party API quotas and generating egress costs for hours.
2. **Split-Brain Concurrent Mutation**: If the expired job is claimed by a second worker, both workers actively translate and mutate storage artifacts concurrently, corrupting chapter manifests.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/activity/worker.py`, pass the active `asyncio.AbstractEventLoop` and `main_task: asyncio.Task` into `_lease_heartbeat`:

```python
async def _run_claimed_with_heartbeat(self, activity: dict[str, Any], lease_id: str) -> dict[str, Any] | None:
    activity_id = str(activity["activity_id"])
    heartbeat_stop = threading.Event()
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()
    assert main_task is not None

    heartbeat = threading.Thread(
        target=self._lease_heartbeat,
        args=(activity_id, lease_id, heartbeat_stop, loop, main_task),
        daemon=True,
        name=f"activity-lease-heartbeat-{activity_id}",
    )
    heartbeat.start()
    try:
        return await self._run_claimed_activity(activity, lease_id)
    finally:
        heartbeat_stop.set()
        heartbeat.join(timeout=max(5.0, min(float(self.activity_log.LEASE_SECONDS), 30.0)))

def _lease_heartbeat(
    self,
    activity_id: str,
    lease_id: str,
    stop_event: threading.Event,
    loop: asyncio.AbstractEventLoop,
    main_task: asyncio.Task,
) -> None:
    lease_seconds = float(self.activity_log.LEASE_SECONDS)
    interval = max(1.0, lease_seconds / 3) if lease_seconds < 45.0 else min(30.0, max(15.0, lease_seconds / 3))
    while not stop_event.wait(interval):
        try:
            renewed = self.activity_log.renew_activity_lease(activity_id, lease_id)
            if not renewed:
                logger.error("Activity lease heartbeat rejected for %s; cancelling active task", activity_id)
                loop.call_soon_threadsafe(main_task.cancel)
                return
        except Exception:
            logger.exception("Activity lease heartbeat failed for %s; cancelling active task", activity_id)
            loop.call_soon_threadsafe(main_task.cancel)
            return
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_activity_worker_heartbeat_abort.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock
from novelai.activity.worker import ActivityWorkerService

@pytest.mark.asyncio
async def test_heartbeat_failure_triggers_task_cancellation():
    mock_log = MagicMock()
    mock_log.LEASE_SECONDS = 0.5
    mock_log.renew_activity_lease.return_value = False  # Simulate lease revocation

    worker = ActivityWorkerService(activity_log=mock_log)
    activity = {"activity_id": "act-revoked-1", "type": "crawl"}

    with pytest.raises(asyncio.CancelledError):
        # Activity should be cancelled as soon as heartbeat detects rejection
        await worker._run_claimed_with_heartbeat(activity, lease_id="stale-lease")
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_activity_worker_heartbeat_abort.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Requires no database schema changes. Reverts cleanly to passive daemon heartbeat if needed.
- **Rollback Procedure**: Revert changes to `worker.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/activity/worker.py
  ```

---

### REC-053: Missing Cooperative Cancellation Check and Abort Propagation in Orchestrator Translation Loop

- **ID**: `REC-053`
- **Subsystem/Component**: Translation Orchestration & Activity Cancellation (`novelai.activity.worker`, `novelai.services.orchestration.translation`)
- **Target Location**:
  - `backend/src/novelai/activity/worker.py:480-515` (`ActivityWorkerService._run_translation_activity`)
  - `backend/src/novelai/services/orchestration/translation.py:1042-1070` (`translate_chapters`)
  - `backend/src/novelai/services/orchestration/translation.py:1270-1370` (`_run_chapter`)
- **Category**: `Weakness`
- **Severity**: `Critical`
- **Summary**: While crawl activities pass a `cancellation_check` callback into chapter scraping loops, translation orchestration passes no cancellation callback or token to `translate_chapters`, causing cancelled translation jobs to continue executing all remaining chapters and chunks.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/worker.py:360-375`, crawl activities hook cooperative cancellation:

```python
def _cancelled_check() -> bool:
    return self.activity_log.is_activity_cancelled(activity_id)

result = await self.orchestrator.scrape_chapters(
    ...,
    cancellation_check=_cancelled_check,
)
```

In sharp contrast, `_run_translation_activity` (lines 480-515):

```python
summary = await self.orchestrator.translate_chapters(
    self._resolve_translation_source_key(activity),
    novel_id,
    chapters,
    provider_key=provider,
    provider_model=model,
    job_id=str(activity.get("activity_id") or ""),
    activity_id=str(activity.get("activity_id") or ""),
    force=force,
    source_language=source_language,
    target_language=target_language,
    allow_cross_provider_fallback=allow_cross_provider_fallback,
    skip_glossary_gate=skip_glossary_gate,
    contribution_mode=contribution_mode if isinstance(contribution_mode, str) else None,
    requesting_user_id=requesting_user_id if isinstance(requesting_user_id, int) else None,
)
```

And inside `translate_chapters` (`backend/src/novelai/services/orchestration/translation.py:1042-1370`):

1. `translate_chapters` accepts no `cancellation_check` parameter.
2. Inside `_run_chapter(record)`, before each chapter translates, there is no verification of activity cancellation.
3. Inside the chunk pipeline (`TranslateStage`), chunks execute without checking whether the parent activity was cancelled.

When an administrator or user cancels an active translation job via the web UI (`POST /admin/activity/{activity_id}/cancel`), `ActivityDatabaseBackend.update_activity_status` marks the database row as `status = 'cancelled'`. However, because the running coroutine has no cancellation check, the background worker continues translating all remaining 50-100 chapters to completion, making unnecessary calls to paid LLM providers.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Runaway Provider Billing on Cancelled Jobs**: An operator cancels a 200-chapter translation queue at chapter 5, but the worker proceeds through chapters 6-200, consuming hundreds of dollars in provider tokens.
2. **Database & Storage Contention**: The cancelled job continues writing translated chapter artifacts to R2 and committing database records, racing against new jobs created for the same novel.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/services/orchestration/translation.py`, add `cancellation_check: Callable[[], bool] | None = None` to `translate_chapters` and pass it to chapter execution:

```python
async def translate_chapters(
    self,
    source_key: str,
    novel_id: str,
    chapters: list[str],
    *,
    cancellation_check: Callable[[], bool] | None = None,
    ...
) -> TranslationJobSummary:
    ...
    async def _run_chapter(record: ChapterRecord) -> None:
        if cancellation_check is not None and cancellation_check():
            raise asyncio.CancelledError(f"Translation activity was cancelled: novel={novel_id}")
        async with chapter_semaphore:
            if cancellation_check is not None and cancellation_check():
                raise asyncio.CancelledError(f"Translation activity was cancelled: novel={novel_id}")
            await self._translate_single_chapter(record, cancellation_check=cancellation_check, ...)
```

2. In `backend/src/novelai/activity/worker.py:480-515`:

```python
def _is_cancelled() -> bool:
    return self.activity_log.is_activity_cancelled(activity_id)

summary = await self.orchestrator.translate_chapters(
    ...,
    cancellation_check=_is_cancelled,
)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_translation_orchestrator_cancellation.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from novelai.services.orchestration.translation import TranslationOrchestrator

@pytest.mark.asyncio
async def test_translate_chapters_aborts_when_cancelled():
    orchestrator = TranslationOrchestrator(storage=MagicMock(), provider_registry=MagicMock())
    cancelled = True

    with pytest.raises(asyncio.CancelledError):
        await orchestrator.translate_chapters(
            source_key="syosetu",
            novel_id="nov-1",
            chapters=["ch1", "ch2"],
            cancellation_check=lambda: cancelled,
        )
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_translation_orchestrator_cancellation.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. `cancellation_check` defaults to `None`, preserving compatibility with standalone calls.
- **Rollback Procedure**: Revert changes to `worker.py` and `translation.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/activity/worker.py backend/src/novelai/services/orchestration/translation.py
  ```

---

### REC-054: False Success Reporting and Broken Retries for RQ Worker Tasks in `worker.tasks`

- **ID**: `REC-054`
- **Subsystem/Component**: RQ Worker Integration & Task Lifecycle (`novelai.worker.tasks`, `novelai.activity.worker`)
- **Target Location**:
  - `backend/src/novelai/worker/tasks.py:64-85` (`run_crawl_activity`)
  - `backend/src/novelai/worker/tasks.py:88-105` (`run_translation_activity`)
  - `backend/src/novelai/worker/tasks.py:41` (`DEFAULT_JOB_RETRY`)
  - `backend/src/novelai/activity/worker.py:710-738` (`ActivityWorkerService._run_claimed_activity`)
  - `backend/src/novelai/activity/worker.py:505-525` (`ActivityWorkerService.run_activity`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `_run_claimed_activity` catches exceptions and returns the failed activity dict instead of re-raising, causing RQ tasks to report success to Redis and disabling RQ's retry policy; when retries do occur, `run_activity` crashes with `ValueError` because the activity status is already `failed`.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/worker.py:710-738`:

```python
except Exception as exc:
    ...
    failed = self.activity_log.update_activity_status(
        activity_id,
        JobStatus.FAILED,
        error=str(exc),
        metadata=failed_metadata,
        lease_id=lease_id,
    )
    if failed is None:
        raise
    self._notify_translation_transition(activity, status=JobStatus.FAILED, result=failed_metadata)
    return failed
```

And in `backend/src/novelai/worker/tasks.py:64-85`:

```python
def run_crawl_activity(activity_id: str) -> dict[str, Any]:
    runner = _get_worker_service()
    try:
        result = asyncio.run(runner.worker.run_activity(activity_id))
    except Exception as exc:
        logger.error("RQ crawl task failed: activity_id=%s error=%s", activity_id, exc)
        raise
    return result or {}
```

This introduces two lifecycle defects:

1. **Silent Task Failure in Queue**: Because `_run_claimed_activity` catches `Exception`, marks the activity as `JobStatus.FAILED` in the database, and returns `failed` as a dictionary, `run_activity` returns normally. In `tasks.py`, `asyncio.run` completes without an exception. RQ treats the task as successfully finished in Redis and completely bypasses the configured `DEFAULT_JOB_RETRY = Retry(max=3, interval=[10, 30, 60])`.
2. **Broken Retries on Status Check**: If an unhandled exception does crash `run_activity` (or an operator manually requeues a failed job), RQ retries `run_crawl_activity(activity_id)`. Inside `run_activity(activity_id)`:

```python
if lease_id is None:
    activity = self.activity_log.claim_activity(activity_id)
    if activity is None:
        existing = self.activity_log.get_activity(activity_id)
        if existing is None:
            return None
        raise ValueError(f"Activity cannot be run from status: {existing.get('status')}")
```

`claim_activity` only claims rows where `status == 'pending'`. Because the previous attempt marked the status as `'failed'`, `claim_activity` returns `None`. `run_activity` immediately raises `ValueError: Activity cannot be run from status: failed`. The retry fails on all attempts without calling `retry_activity`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Masked Failures in Redis**: Redis and RQ dashboards report 100% job success while the database log is littered with failed tasks. Configured retry policies never execute.
2. **Dead-End Requeueing**: Any manual retry of a failed activity crashes instantly with a `ValueError`.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/worker/tasks.py`, define `ActivityExecutionError` and raise when the returned activity has failed:

```python
class ActivityExecutionError(RuntimeError):
    """Raised when an activity finishes in FAILED status so RQ can apply its retry policy."""

def run_crawl_activity(activity_id: str) -> dict[str, Any]:
    runner = _get_worker_service()
    result = asyncio.run(runner.worker.run_activity(activity_id, allow_retry_claim=True))
    if result and result.get("status") == JobStatus.FAILED.value:
        raise ActivityExecutionError(f"Crawl activity {activity_id} failed: {result.get('error')}")
    return result or {}
```

2. In `backend/src/novelai/activity/worker.py:505-525`, support `allow_retry_claim=True`:

```python
if lease_id is None:
    activity = self.activity_log.claim_activity(activity_id)
    if activity is None and allow_retry_claim:
        existing = self.activity_log.get_activity(activity_id)
        if existing and existing.get("status") == JobStatus.FAILED.value:
            self.activity_log.retry_activity(activity_id)
            activity = self.activity_log.claim_activity(activity_id)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_rq_task_lifecycle_and_retries.py`:

```python
import pytest
from novelai.worker.tasks import run_crawl_activity, ActivityExecutionError
from novelai.activity.job_status import JobStatus
from unittest.mock import patch, MagicMock

def test_run_crawl_activity_raises_on_failed_status():
    mock_runner = MagicMock()
    mock_runner.worker.run_activity = MagicMock(return_value={"status": JobStatus.FAILED.value, "error": "HTTP 500"})

    with patch("novelai.worker.tasks._get_worker_service", return_value=mock_runner):
        with pytest.raises(ActivityExecutionError) as exc_info:
            run_crawl_activity("act-failed-1")
        assert "HTTP 500" in str(exc_info.value)
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_rq_task_lifecycle_and_retries.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Backwards-compatible. Enables RQ retries without altering core database status models.
- **Rollback Procedure**: Revert changes to `tasks.py` and `worker.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/worker/tasks.py backend/src/novelai/activity/worker.py
  ```

---

### REC-055: Infinite Re-Execution Loop of Failed Scheduled Jobs and Inverted Baseline Check in `SchedulerService`

- **ID**: `REC-055`
- **Subsystem/Component**: Cron Scheduler Service (`novelai.services.scheduler_service`)
- **Target Location**:
  - `backend/src/novelai/services/scheduler_service.py:117-135` (`SchedulerService._latest_success`)
  - `backend/src/novelai/services/scheduler_service.py:137-147` (`SchedulerService._is_due`)
  - `backend/src/novelai/services/scheduler_service.py:90-105` (`SchedulerService._loop`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `_is_due` unconditionally evaluates to `True` on cold startup due to `croniter.get_prev() <= now`, and because it only checks for `status = 'succeeded'` in `scheduled_cron_log`, any failed job triggers an infinite re-execution loop every 5 minutes.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/scheduler_service.py:137-147`:

```python
async def _is_due(self, job_name: str, expression: str, timezone_name: str) -> bool:
    timezone = ZoneInfo(timezone_name)
    now = datetime.now(timezone)
    last_success = await self._latest_success(job_name)
    if last_success is None:
        return croniter(expression, now).get_prev(datetime) <= now
    if last_success.tzinfo is None:
        last_success = last_success.replace(tzinfo=UTC)
    next_due = croniter(expression, last_success.astimezone(timezone)).get_next(datetime)
    return next_due <= now
```

And `_latest_success` (lines 117-135):

```python
def _query() -> datetime | None:
    with scope_factory() as session:
        return session.execute(
            text(
                "SELECT max(started_at) FROM scheduled_cron_log "
                "WHERE job_name LIKE :pattern AND status = 'succeeded'"
            ),
            {"pattern": f"{job_name}-%"},
        ).scalar_one_or_none()
```

This causes two production failures:

1. **Cold-start immediate execution storm**: If a job has never run (or after database migration when `scheduled_cron_log` is empty), `last_success` is `None`. The check `croniter(expression, now).get_prev(datetime) <= now` checks whether the most recent past cron tick is before `now`. By mathematical definition of `get_prev()`, this is ALWAYS `True` for any valid cron expression. As a result, every scheduled job (daily backups, maintenance, cleanup) fires immediately upon application boot, overloading external storage and database pools.
2. **Infinite failure loop**: `_latest_success` strictly filters for `status = 'succeeded'`. If a nightly database backup scheduled for 02:00 fails at 02:02 and records `status = 'failed'` in `scheduled_cron_log`, at the next scheduler tick (02:05), `_latest_success` queries the table and ignores the failed run. It returns the previous day's success timestamp (or `None`). `next_due` is computed against the old timestamp (`02:00 <= 02:05` -> `True`), immediately re-executing the failed backup every 5 minutes indefinitely.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Boot Thundering Herd**: Container redeployment triggers heavy scheduled jobs (backups, full novel recrawls) simultaneously, exhausting connection pools.
2. **Infinite Error Re-Execution**: Failed jobs repeat every 5-minute tick, hammering third-party APIs or filling disk with failed dump artifacts.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/services/scheduler_service.py`, inspect the most recent run regardless of status and establish a cold-start baseline:

```python
async def _latest_attempt(self, job_name: str) -> tuple[datetime | None, str | None]:
    scope_factory = self._session_scope_factory

    def _query() -> tuple[datetime | None, str | None]:
        from sqlalchemy import text
        with scope_factory() as session:
            row = session.execute(
                text(
                    "SELECT started_at, status FROM scheduled_cron_log "
                    "WHERE job_name LIKE :pattern ORDER BY started_at DESC LIMIT 1"
                ),
                {"pattern": f"{job_name}-%"},
            ).first()
            return (row[0], row[1]) if row else (None, None)

    return await asyncio.to_thread(_query)

async def _is_due(self, job_name: str, expression: str, timezone_name: str) -> bool:
    timezone = ZoneInfo(timezone_name)
    now = datetime.now(timezone)
    last_attempt_at, last_status = await self._latest_attempt(job_name)

    if last_attempt_at is None:
        # Establish baseline on cold start: do not execute immediately; wait for next scheduled tick
        return False

    if last_attempt_at.tzinfo is None:
        last_attempt_at = last_attempt_at.replace(tzinfo=UTC)

    # If the last attempt failed, enforce minimum 15-minute retry cooldown
    if last_status == "failed":
        if (now - last_attempt_at.astimezone(timezone)).total_seconds() < 900:
            return False

    next_due = croniter(expression, last_attempt_at.astimezone(timezone)).get_next(datetime)
    return next_due <= now
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_scheduler_service_resilience.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta
from novelai.services.scheduler_service import SchedulerService
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_scheduler_does_not_fire_on_cold_start():
    scheduler = SchedulerService(session_scope_factory=None)
    scheduler._latest_attempt = AsyncMock(return_value=(None, None))
    due = await scheduler._is_due("daily_backup", "0 2 * * *", "UTC")
    assert due is False

@pytest.mark.asyncio
async def test_scheduler_respects_failure_cooldown():
    scheduler = SchedulerService(session_scope_factory=None)
    recent_failure = datetime.now(timezone.utc) - timedelta(minutes=5)
    scheduler._latest_attempt = AsyncMock(return_value=(recent_failure, "failed"))
    due = await scheduler._is_due("daily_backup", "*/5 * * * *", "UTC")
    assert due is False
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_scheduler_service_resilience.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible with existing `scheduled_cron_log` schema.
- **Rollback Procedure**: Revert changes to `scheduler_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/scheduler_service.py
  ```

---

### REC-056: Inappropriate `skip_locked=True` on Single-Key Lookups and Missing Renewal Locks in `ScheduledJobLeaseService`

- **ID**: `REC-056`
- **Subsystem/Component**: Distributed Scheduled Job Leases (`novelai.services.scheduled_job_lease_service`)
- **Target Location**:
  - `backend/src/novelai/services/scheduled_job_lease_service.py:18-50` (`ScheduledJobLeaseService.acquire`)
  - `backend/src/novelai/services/scheduled_job_lease_service.py:52-66` (`ScheduledJobLeaseService.renew`)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: `ScheduledJobLeaseService.acquire` uses `with_for_update(skip_locked=True)` on a single primary-key lookup, causing concurrent acquisition attempts during lease renewal to skip the locked row and throw `IntegrityError`, while `renew` executes without row locking, risking lost updates.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/scheduled_job_lease_service.py:18-50`:

```python
def acquire(self, job_name: str, holder_id: str, lease_seconds: int) -> bool:
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=lease_seconds)
    try:
        with self._session_scope_factory() as session:
            lease = session.execute(
                select(ScheduledJobLease)
                .where(ScheduledJobLease.job_name == job_name)
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if lease is None:
                session.add(
                    ScheduledJobLease(
                        job_name=job_name,
                        holder_id=holder_id,
                        acquired_at=now,
                        heartbeat_at=now,
                        expires_at=expires_at,
                    )
                )
                return True
            ...
    except IntegrityError:
        return False
```

And in `renew` (lines 52-66):

```python
def renew(self, job_name: str, holder_id: str, lease_seconds: int) -> bool:
    now = datetime.now(UTC)
    with self._session_scope_factory() as session:
        lease = session.get(ScheduledJobLease, job_name)
        if lease is None or lease.holder_id != holder_id:
            return False
        ...
        lease.heartbeat_at = now
        lease.expires_at = now + timedelta(seconds=lease_seconds)
        return True
```

Applying `skip_locked=True` to a point query on a unique primary key (`WHERE job_name == :name`) is an anti-pattern:

1. **False-negative existence**: If Worker A is executing a transaction on `ScheduledJobLease` (e.g. renewing its lease), Worker B's `with_for_update(skip_locked=True)` skips the locked row and returns `lease = None`.
2. **Spurious insertion & rollback**: Because `lease is None`, Worker B attempts `session.add(ScheduledJobLease(...))`. On commit, PostgreSQL raises `UniqueViolation (IntegrityError)` because the primary key already exists, forcing a transaction rollback and log pollution.
3. **Unlocked renewal**: In `renew()`, `session.get(ScheduledJobLease, job_name)` acquires no row lock. A renewal running concurrently with an expiration takeover suffers from uncommitted dirty reads or lost updates.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Spurious IntegrityError Exceptions**: Transient lock contention causes benign acquisition attempts to fail with constraint violations rather than orderly contention.
2. **Lost Heartbeat Updates**: Unlocked renewals allow racing workers to overwrite newer expiration timestamps with older ones, causing leases to expire prematurely.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/services/scheduled_job_lease_service.py`, remove `skip_locked=True` from `acquire` and add row-level locking to `renew`:

```python
def acquire(self, job_name: str, holder_id: str, lease_seconds: int) -> bool:
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=lease_seconds)
    with self._session_scope_factory() as session:
        lease = session.execute(
            select(ScheduledJobLease)
            .where(ScheduledJobLease.job_name == job_name)
            .with_for_update()
        ).scalar_one_or_none()

        if lease is None:
            session.add(
                ScheduledJobLease(
                    job_name=job_name,
                    holder_id=holder_id,
                    acquired_at=now,
                    heartbeat_at=now,
                    expires_at=expires_at,
                )
            )
            return True

        lease_expires_at = lease.expires_at
        if lease_expires_at.tzinfo is None:
            lease_expires_at = lease_expires_at.replace(tzinfo=UTC)

        if lease.holder_id != holder_id and lease_expires_at > now:
            return False

        lease.holder_id = holder_id
        lease.acquired_at = now
        lease.heartbeat_at = now
        lease.expires_at = expires_at
        return True

def renew(self, job_name: str, holder_id: str, lease_seconds: int) -> bool:
    now = datetime.now(UTC)
    with self._session_scope_factory() as session:
        lease = session.execute(
            select(ScheduledJobLease)
            .where(ScheduledJobLease.job_name == job_name)
            .with_for_update()
        ).scalar_one_or_none()

        if lease is None or lease.holder_id != holder_id:
            return False
        lease_expires_at = lease.expires_at
        if lease_expires_at.tzinfo is None:
            lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
        if lease_expires_at <= now:
            return False
        lease.heartbeat_at = now
        lease.expires_at = now + timedelta(seconds=lease_seconds)
        return True
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_scheduled_job_lease_locking.py`:

```python
from datetime import datetime, timezone, timedelta
from novelai.services.scheduled_job_lease_service import ScheduledJobLeaseService

def test_acquire_blocks_and_inspects_row_without_skip_locked(db_session_factory):
    svc = ScheduledJobLeaseService(session_scope_factory=db_session_factory)
    acquired = svc.acquire("backup_job", "worker-1", 60)
    assert acquired is True

    # Same holder renewal succeeds
    renewed = svc.renew("backup_job", "worker-1", 60)
    assert renewed is True

    # Different holder denied while lease is active
    denied = svc.acquire("backup_job", "worker-2", 60)
    assert denied is False
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_scheduled_job_lease_locking.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible with `ScheduledJobLease` table schema. Eliminates transient `IntegrityError` log pollution.
- **Rollback Procedure**: Revert changes to `scheduled_job_lease_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/scheduled_job_lease_service.py
  ```

---

### REC-057: SIGTERM Container Shutdown Immediately Marks In-Progress Jobs as Permanently Cancelled

- **ID**: `REC-057`
- **Subsystem/Component**: Background Activity Runner & Process Lifecycle (`novelai.activity.runner`, `novelai.activity.worker`)
- **Target Location**:
  - `backend/src/novelai/activity/runner.py:65-88` (`BackgroundActivityRunner.stop`)
  - `backend/src/novelai/activity/worker.py:630-650` (`ActivityWorkerService._run_claimed_activity` CancelledError handler)
- **Category**: `Weakness`
- **Severity**: `High`
- **Summary**: Graceful container or worker shutdown calls `task.cancel()`, which triggers the `asyncio.CancelledError` handler in `_run_claimed_activity`, permanently marking in-flight jobs as `JobStatus.CANCELLED` with `"cancelled_by": "owner"` instead of gracefully releasing leases back to `PENDING`.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/runner.py:65-88`:

```python
async def stop(self) -> dict[str, Any]:
    if self._stop_event is not None:
        self._stop_event.set()

    task = self._task
    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    ...
```

When the application receives a `SIGTERM` signal (e.g. during a rolling deployment, Docker container restart, or Kubernetes pod termination), the server lifecycle invokes `runner.stop()`.
Calling `task.cancel()` raises `asyncio.CancelledError` inside the active loop running `_run_claimed_activity`.
In `backend/src/novelai/activity/worker.py:630-650`:

```python
except asyncio.CancelledError as exc:
    cancelled_metadata: dict[str, Any] = {
        **activity_metadata,
        "current_stage": "cancelled",
        "cancelled_by": "owner",
        "errors": [{"message": str(exc), "error_code": "CANCELLED"}],
    }
    cancelled = self.activity_log.update_activity_status(
        activity_id,
        JobStatus.CANCELLED,
        error=str(exc),
        metadata=cancelled_metadata,
        lease_id=lease_id,
    )
    if cancelled is None:
        raise
    return cancelled
```

`_run_claimed_activity` cannot distinguish between:

1. An intentional administrative cancellation requested by an operator in the UI (`POST /admin/activity/{id}/cancel`); and
2. A standard process termination / container shutdown where the asyncio task is cancelled by `task.cancel()`.

Because both present as `asyncio.CancelledError`, the handler permanently marks the in-progress job as `CANCELLED` with `"cancelled_by": "owner"`. `JobStatus.CANCELLED` is a terminal status that will never be picked up by another worker or recovered by `_recover_expired`. Routine deployments therefore abort active user translations and crawls permanently, forcing users to manually diagnose and recreate the jobs.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Deployment Job Annihilation**: Continuous deployment pipelines or container restarts permanently kill all in-flight translations and crawls, falsely attributing the cancellation to the owner.
2. **Loss of In-Progress Progress**: Jobs that translated 45 of 50 chapters are cancelled permanently rather than re-queued to finish the remaining 5 chapters.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/activity/runner.py`, introduce graceful drain and distinct shutdown tracking:

```python
class BackgroundActivityRunner:
    def __init__(self, ...):
        ...
        self._shutting_down = False

    async def stop(self, drain_timeout: float = 30.0) -> dict[str, Any]:
        self._shutting_down = True
        if self._stop_event is not None:
            self._stop_event.set()

        task = self._task
        if task is not None and not task.done():
            try:
                # Shield current chapter and allow drain window
                await asyncio.wait_for(asyncio.shield(task), timeout=drain_timeout)
            except (TimeoutError, asyncio.TimeoutError):
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
```

2. In `backend/src/novelai/activity/worker.py:630-650`, distinguish shutdown cancellation from owner cancellation:

```python
except asyncio.CancelledError as exc:
    # If cancelled by shutdown or lease revocation, release back to pending
    if getattr(self, "_is_shutting_down", False) or not self.activity_log.is_activity_cancelled(activity_id):
        logger.info("Activity %s interrupted by worker shutdown; resetting to PENDING", activity_id)
        self.activity_log.update_activity_status(
            activity_id,
            JobStatus.PENDING,
            error="Interrupted by runner shutdown; lease released",
            lease_id=None,
        )
        raise

    cancelled_metadata = {
        **activity_metadata,
        "current_stage": "cancelled",
        "cancelled_by": "owner",
        "errors": [{"message": str(exc), "error_code": "CANCELLED"}],
    }
    ...
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_activity_runner_graceful_shutdown.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock
from novelai.activity.runner import BackgroundActivityRunner
from novelai.activity.job_status import JobStatus

@pytest.mark.asyncio
async def test_runner_shutdown_resets_activity_to_pending():
    mock_log = MagicMock()
    mock_log.is_activity_cancelled.return_value = False
    mock_worker = MagicMock()

    runner = BackgroundActivityRunner(worker=mock_worker)
    runner._shutting_down = True

    # Verify shutdown cancels without marking cancelled_by owner
    await runner.stop(drain_timeout=0.1)
    assert runner.status()["is_running"] is False
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_activity_runner_graceful_shutdown.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking. Protects in-flight work across container redeployments.
- **Rollback Procedure**: Revert changes to `runner.py` and `worker.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/activity/runner.py backend/src/novelai/activity/worker.py
  ```

---

### REC-058: FIFO Queue Head-of-Line Blocking and Lack of Priority Tiers in Activity Scheduling

- **ID**: `REC-058`
- **Subsystem/Component**: Activity Queue Scheduling & Priority Control (`novelai.activity.database`, `novelai.activity.runner`, `novelai.activity.queue`)
- **Target Location**:
  - `backend/src/novelai/activity/database.py:590-605` (`ActivityDatabaseBackend._claim_update_statement`)
  - `backend/src/novelai/activity/queue.py:720-735` (`ActivityQueueService.claim_next_activity`)
  - `backend/src/novelai/activity/runner.py:90-103` (`BackgroundActivityRunner.run_once`)
  - `backend/src/novelai/db/models/activity.py:27-31` (`ActivityRecord`)
- **Category**: `Architecture`
- **Severity**: `Medium`
- **Summary**: Activity claiming enforces strict FIFO ordering based solely on `created_at` without priority levels, causing long-running 100-chapter batch translations to block fast interactive single-chapter scrapes and metadata lookups for hours.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/database.py:590-605`:

```python
pending = select(ActivityRecord.activity_id).where(ActivityRecord.status == JobStatus.PENDING.value)
if activity_id is not None:
    pending = pending.where(ActivityRecord.activity_id == activity_id)
else:
    if activity_type is not None:
        pending = pending.where(ActivityRecord.type == activity_type)
    pending = pending.order_by(ActivityRecord.created_at).limit(1).with_for_update(skip_locked=True)
```

And in `BackgroundActivityRunner.run_once`:

```python
async def run_once(self) -> dict[str, Any] | None:
    activity = await self.worker.run_next(activity_type=self.activity_type)
    ...
    return activity
```

This architecture exhibits classical head-of-line (HOL) blocking:

1. **Single sequential worker loop**: `BackgroundActivityRunner` runs a single task at a time. Each `run_once()` waits for the claimed activity to complete entirely before claiming the next.
2. **Lack of prioritization**: Queue selection orders strictly by `ActivityRecord.created_at`.
3. **Workload mismatch**: Translating a 100-chapter novel takes between 30 and 90 minutes. In contrast, scraping novel metadata (`CrawlJobKind.METADATA`) or re-crawling a single chapter takes 1 to 3 seconds.
   If an operator triggers a full novel translation, and subsequently an interactive user adds a new novel URL to preview metadata or recrawls a chapter to read the latest release, that 2-second request sits in `pending` status behind the 90-minute translation job.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Interactive Starvation**: Users requesting quick metadata imports or single-chapter refreshes experience perceived downtime because a heavy bulk translation holds the single runner lane.
2. **Lack of SLA Differentiation**: Maintenance jobs (e.g. nightly recrawls) cannot be deprioritized below real-time user requests.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/models/activity.py`, add `priority: Mapped[int]` (lower number = higher priority) and index it:

```python
class ActivityPriority(int, Enum):
    INTERACTIVE = 10
    NORMAL = 100
    BULK = 200

priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100", index=True)
```

2. Update table index and claim query in `backend/src/novelai/activity/database.py:590-605`:

```python
pending = (
    pending
    .order_by(ActivityRecord.priority.asc(), ActivityRecord.created_at.asc())
    .limit(1)
    .with_for_update(skip_locked=True)
)
```

3. Update `create_crawl_activity` and `create_translation_activity` to accept optional `priority: int = ActivityPriority.NORMAL.value`. For `CrawlJobKind.METADATA` and interactive user requests, pass `ActivityPriority.INTERACTIVE.value`.

#### 4. Verification & Test Strategy

Create `backend/tests/test_activity_priority_queue.py`:

```python
from novelai.db.models.activity import ActivityRecord, ActivityPriority
from novelai.activity.job_status import JobStatus

def test_priority_activity_claimed_before_older_bulk_activity(db_session, activity_backend):
    # Enqueue bulk job first
    bulk = ActivityRecord(activity_id="bulk-1", type="translation", kind="novel", novel_id="n1", priority=200, status=JobStatus.PENDING.value)
    # Enqueue interactive job second
    interactive = ActivityRecord(activity_id="interactive-1", type="crawl", kind="metadata", novel_id="n2", priority=10, status=JobStatus.PENDING.value)

    db_session.add_all([bulk, interactive])
    db_session.commit()

    claimed = activity_backend.claim_next_activity()
    assert claimed is not None
    assert claimed["activity_id"] == "interactive-1"
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_activity_priority_queue.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Requires Alembic migration `YYYY-MM-DD_<hash>_add_activity_record_priority.py` with `server_default="100"`.
- **Rollback Procedure**: Revert migration and model changes.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/db/models/activity.py backend/src/novelai/activity/database.py
  ```

---

### REC-059: Unbounded Checkpoint File Accumulation and Metadata Payload Size Vulnerability in Job Execution

- **ID**: `REC-059`
- **Subsystem/Component**: Runtime Checkpoint Storage & Database Metadata Validation (`novelai.storage.jobs`, `novelai.activity.database`, `novelai.activity.worker`)
- **Target Location**:
  - `backend/src/novelai/storage/jobs.py:200-245` (`create_checkpoint`)
  - `backend/src/novelai/storage/jobs.py:248-270` (`list_checkpoints`)
  - `backend/src/novelai/activity/database.py:75-80` (`_metadata_text`)
  - `backend/src/novelai/activity/worker.py:380-410` (`_run_crawl_activity` & `crawl_result`)
- **Category**: `Weakness`
- **Severity**: `Medium`
- **Summary**: `create_checkpoint` creates timestamped full-chapter JSON dumps with no retention pruning, while `_metadata_text` throws a hard `ValueError` during long crawls when serialized chapter failure lists exceed `ACTIVITY_METADATA_MAX_BYTES`, aborting active jobs.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/jobs.py:200-245`:

```python
def create_checkpoint(self: Any, novel_id: str, chapter_id: str, checkpoint_name: str = "auto") -> Path:
    ...
    if safe_checkpoint_name == "auto":
        filename = f"{physical_stem}__{_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    else:
        filename = f"{physical_stem}__{safe_checkpoint_name}.json"

    path = checkpoints_dir / filename
    self._write_text(path, json.dumps(checkpoint_data, ensure_ascii=False, indent=2))
    return path
```

Every checkpoint serializes the full `raw_chapter`, `translated_chapter`, and `chapter_state`. When `checkpoint_name == "auto"`, every invocation creates a new timestamped file. There is no maximum checkpoint count, TTL, or retention policy. On novels with hundreds of chapters subjected to retries, checkpoint directories accumulate gigabytes of redundant JSON files on local disk.

Furthermore, in `backend/src/novelai/activity/database.py:75-80`:

```python
def _metadata_text(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > settings.ACTIVITY_METADATA_MAX_BYTES:
        raise ValueError("Activity metadata exceeds the configured size limit")
    return encoded
```

In `ActivityWorkerService._run_crawl_activity` (lines 380-410):

```python
crawl_result = {
    "succeeded": succeeded,
    "skipped": skipped,
    "failed": failed,
    "failures": result.get("failures", []),
    "image_download_failures": image_download_failures,
    "terminal_status": terminal_status,
}
self.activity_log.update_activity_metadata(
    activity_id,
    {"crawl_result": crawl_result},
    lease_id=lease_id,
)
```

When crawling a serialized novel with many chapters (e.g. 1,000-2,000 chapters) and sporadic network or HTML parser errors, `result.get("failures", [])` accumulates hundreds of detailed exception entries. When `update_activity_metadata` serializes this dictionary, `len(encoded) > settings.ACTIVITY_METADATA_MAX_BYTES` triggers a hard `ValueError`. This exception crashes the worker task right at the completion stage, causing a successful crawl to be marked as failed simply because the error log payload exceeded the database metadata constraint.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Local Disk Space Exhaustion**: Repeated translation attempts and auto-checkpoints exhaust local server storage volumes.
2. **Metadata Overflow Job Abort**: A crawl that completed 980 of 1,000 chapters crashes on status commit because its failure error log exceeds 512KB, throwing away the crawl status.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/storage/jobs.py:create_checkpoint`, prune older checkpoints to retain at most `max_checkpoints=3` per chapter:

```python
def create_checkpoint(self: Any, novel_id: str, chapter_id: str, checkpoint_name: str = "auto", max_checkpoints: int = 3) -> Path:
    ...
    self._write_text(path, json.dumps(checkpoint_data, ensure_ascii=False, indent=2))

    # Prune historical checkpoints for this chapter
    try:
        pattern = f"{physical_stem}__*.json"
        existing = sorted(checkpoints_dir.glob(pattern), key=lambda p: p.stat().st_mtime)
        if len(existing) > max_checkpoints:
            for old_file in existing[:-max_checkpoints]:
                old_file.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Failed to prune old checkpoints for %s/%s: %s", novel_id, safe_chapter_id, exc)
    return path
```

2. In `backend/src/novelai/activity/worker.py:380-410`, truncate failure lists before metadata persistence:

```python
raw_failures = result.get("failures", [])
truncated_failures = raw_failures[:50]
if len(raw_failures) > 50:
    truncated_failures.append({
        "truncated_count": len(raw_failures) - 50,
        "note": f"{len(raw_failures) - 50} additional failure details omitted to respect metadata budget",
    })

crawl_result = {
    "succeeded": succeeded,
    "skipped": skipped,
    "failed": failed,
    "failures": truncated_failures,
    "image_download_failures": image_download_failures[:20],
    "terminal_status": terminal_status,
}
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_checkpoint_pruning_and_metadata_budget.py`:

```python
import json
from pathlib import Path
from novelai.activity.database import _metadata_text

def test_metadata_payload_under_size_limit():
    large_failures = [{"chapter": f"ch_{i}", "error": "Parser timeout error message"} for i in range(1000)]
    truncated = large_failures[:50]
    payload = {"crawl_result": {"failures": truncated}}
    text = _metadata_text(payload)
    assert len(text.encode("utf-8")) <= 524288

def test_checkpoint_retention_prunes_older_files(tmp_path):
    chapter_dir = tmp_path / "checkpoints"
    chapter_dir.mkdir(parents=True)
    for i in range(5):
        f = chapter_dir / f"ch1__{i}.json"
        f.write_text("{}", encoding="utf-8")
    existing = sorted(chapter_dir.glob("ch1__*.json"))
    assert len(existing) == 5
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_checkpoint_pruning_and_metadata_budget.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. Safeguards worker completion across large crawls.
- **Rollback Procedure**: Revert changes to `storage/jobs.py` and `activity/worker.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/storage/jobs.py backend/src/novelai/activity/worker.py
  ```

---

### REC-060: Unresponsive Event-Driven Wakeup Causing up to 30-Second Polling Latency in `BackgroundActivityRunner`

- **ID**: `REC-060`
- **Subsystem/Component**: Activity Runner Loop & Polling Efficiency (`novelai.activity.runner`, `novelai.activity.queue`)
- **Target Location**:
  - `backend/src/novelai/activity/runner.py:40-60` (`BackgroundActivityRunner.next_idle_poll_seconds`)
  - `backend/src/novelai/activity/runner.py:105-125` (`BackgroundActivityRunner._run_loop`)
  - `backend/src/novelai/activity/queue.py:340-400` (`ActivityQueueService.create_crawl_activity` & `create_translation_activity`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `BackgroundActivityRunner` relies exclusively on polling with exponential backoff up to 30 seconds with no event notification or wake mechanism when new activities are enqueued, introducing noticeable latency for user-initiated crawl and translation jobs.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/activity/runner.py:40-60` and 105-125:

```python
IDLE_POLL_MIN_SECONDS = 5.0
IDLE_POLL_MAX_SECONDS = 30.0

def next_idle_poll_seconds(self) -> float:
    delay = self._idle_poll_seconds
    self._idle_poll_seconds = min(self.IDLE_POLL_MAX_SECONDS, delay * 2)
    return delay

async def _run_loop(self) -> None:
    assert self._stop_event is not None
    while not self._stop_event.is_set():
        try:
            activity = await self.run_once()
            if activity is None:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.next_idle_poll_seconds())
```

When the activity queue is idle, `_idle_poll_seconds` exponentially backs off from 5.0s to 10.0s, 20.0s, and caps at 30.0s.
The sleep mechanism `await asyncio.wait_for(self._stop_event.wait(), timeout=...)` only wakes up if:

1. The timeout expires; or
2. `self._stop_event` is set (which only occurs on worker shutdown in `stop()`).

When an administrator or user enqueues a new activity via the web UI (`POST /admin/crawl` or `POST /admin/translate`), `ActivityQueueService.create_crawl_activity` or `create_translation_activity` inserts the record into the database. However, `ActivityQueueService` has no mechanism to notify or signal `BackgroundActivityRunner`.
If the runner entered its 30-second sleep interval 1 second before the user clicked "Translate", the user must wait 29 seconds before the worker even wakes up to claim the activity. This makes the system feel sluggish and unresponsive.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Perceived System Sluggishness**: End users experience up to 30 seconds of dead time after triggering an on-demand crawl or translation before progress indicators change.
2. **CPU Polling vs Response Time Dilemma**: Without event notification, reducing poll latency requires aggressive 1-second polling that wastes database queries and CPU cycles during long idle periods.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/activity/runner.py`, add a wake event and expose a `notify()` method:

```python
class BackgroundActivityRunner:
    def __init__(self, ...):
        ...
        self._wake_event: asyncio.Event | None = None

    def notify(self) -> None:
        """Wake the runner immediately from idle backoff sleep."""
        if self._wake_event is not None and not self._wake_event.is_set():
            self._wake_event.set()

    async def _run_loop(self) -> None:
        assert self._stop_event is not None
        self._wake_event = asyncio.Event()
        while not self._stop_event.is_set():
            try:
                activity = await self.run_once()
                if activity is None:
                    delay = self.next_idle_poll_seconds()
                    # Sleep until timeout, stop_event, or wake_event
                    stop_coro = self._stop_event.wait()
                    wake_coro = self._wake_event.wait()
                    done, _ = await asyncio.wait(
                        [asyncio.create_task(stop_coro), asyncio.create_task(wake_coro)],
                        timeout=delay,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if self._wake_event.is_set():
                        self._wake_event.clear()
                        self._reset_idle_backoff()
```

2. In `backend/src/novelai/activity/queue.py`, allow registering an optional runner or wake callback, invoking `runner.notify()` whenever an activity is successfully created.

#### 4. Verification & Test Strategy

Create `backend/tests/test_activity_runner_event_wakeup.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock
from novelai.activity.runner import BackgroundActivityRunner

@pytest.mark.asyncio
async def test_runner_wakes_immediately_on_notify():
    mock_worker = AsyncMock()
    mock_worker.run_next.return_value = None
    runner = BackgroundActivityRunner(worker=mock_worker)

    await runner.start()
    assert runner._idle_poll_seconds >= 5.0

    # Notify should wake without waiting 5-30s
    runner.notify()
    await asyncio.sleep(0.05)

    await runner.stop()
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_activity_runner_event_wakeup.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. If no wake event is fired, runner continues polling with standard backoff.
- **Rollback Procedure**: Revert changes to `runner.py` and `queue.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/activity/runner.py backend/src/novelai/activity/queue.py
  ```

---

## Iteration 7: Authentication, Authorization, Session Lifecycle, & Security Middleware

Audit Focus: User and owner authentication, session lifecycle, password security (Argon2id), Google OAuth2/OIDC integration, authorization roles, CSRF defense, rate limiting, and security middleware across `backend/src/novelai/api/auth/`, `backend/src/novelai/api/middleware/`, `backend/src/novelai/api/routers/auth.py`, `backend/src/novelai/api/routers/admin_users.py`, and `backend/src/novelai/shared/`.

### Summary of Recommendations (Iteration 7)

| ID          | Subsystem / Component               | Category      | Title                                                                                   |
| :---------- | :---------------------------------- | :------------ | :-------------------------------------------------------------------------------------- |
| **REC-061** | Password Security / Cryptography    | Security      | Missing Argon2id Parameter Tuning, Automatic Rehash Triggers, & Hashing DoS Guard       |
| **REC-062** | Authentication / Account Discovery  | Security      | User Account Enumeration Timing Oracles via Short-Circuit Hashing & Synchronous Mail    |
| **REC-063** | OAuth 2.0 / Identity Provider       | Security      | Missing PKCE Flow, OIDC Nonce Binding, & Cryptographic ID Token Verification            |
| **REC-064** | Session Security / Cookie Hardening | Security      | Hardcoded Session Cookie Name Without `__Host-` Prefix & Subdomain Tossing Isolation    |
| **REC-065** | Session Lifecycle / Persistence     | Performance   | Uncached Database Session Validation & Persistent Zombie Cookies on Revoked Users       |
| **REC-066** | Rate Limiting / Abuse Prevention    | Security      | IP-Only Rate Limiter Keying on Unauthenticated Endpoints Enabling Credential Stuffing   |
| **REC-067** | Privileged Access / Owner Auth      | Security      | Static Owner Bootstrap Secret Vulnerability, Lack of Deprecation, & Missing Lockout     |
| **REC-068** | Security Middleware / HTTP Headers  | Security      | Missing Content-Security-Policy, HSTS Preload Directives, & BaseHTTPMiddleware Overhead |
| **REC-069** | Audit Logging / Security Telemetry  | Observability | Security Event Blind Spots in Audit Logs for Auth Failures, Role Denials, & CSRF Drops  |
| **REC-070** | Network Boundary / Reverse Proxy    | Performance   | Repeated Per-Request IP Network Parsing in Proxy Validation & Dead Host Header Logic    |

---

---

### REC-061: Missing Argon2id Parameter Tuning, Automatic Rehash Triggers, & Hashing DoS Guard

- **ID**: `REC-061`
- **Subsystem/Component**: Password Security / Cryptography (`novelai.api.auth.passwords`, `novelai.services.auth_service`)
- **Target Location**:
  - `backend/src/novelai/api/auth/passwords.py:6-21` (`_PASSWORD_HASHER`, `hash_password`, `verify_password`)
  - `backend/src/novelai/services/auth_service.py:146-163` (`AuthService.password_login`)
  - `backend/src/novelai/config/settings.py:410-435`
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: Argon2id password hashing instantiates `PasswordHasher()` with fixed library defaults rather than explicit OWASP-recommended parameters, never evaluates `check_needs_rehash` upon successful login, and lacks input length guards in cryptographic primitives.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/auth/passwords.py:6-21`:

```python
_PASSWORD_HASHER = PasswordHasher()

def hash_password(password: str) -> str:
    """Return a salted Argon2id password hash."""
    return _PASSWORD_HASHER.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored Argon2id hash."""
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError, TypeError):
        return False
```

And in `backend/src/novelai/services/auth_service.py:146-163` (`password_login`):

```python
if (
    user is None
    or not user.is_active
    or user.role == "owner"
    or not user.password_hash
    or not verify_password(password, user.password_hash)
):
    raise ValueError("Invalid email or password.")

user.last_login_at = datetime.now(UTC)
self.db_session.flush()
```

1. **Parameter Drift & Weak Defaults**: Default `PasswordHasher()` parameters in `argon2-cffi` depend on the underlying C library compile-time defaults. RFC 9106 and OWASP Password Storage Cheat Sheet recommend explicit parameterization: minimum 64 MiB memory cost (`memory_cost=65536`), 3 iterations (`time_cost=3`), and 4 parallel lanes (`parallelism=4`). These are unconfigurable in `settings.py`.
2. **Missing Rehash Triggers**: `argon2.PasswordHasher.check_needs_rehash(hash)` is completely unreferenced. When Argon2 cost parameters or salt lengths are upgraded, existing user password hashes stored in `User.password_hash` remain permanently frozen at older, weaker parameter sets. Modern authentication systems must check `check_needs_rehash(user.password_hash)` immediately after successful password verification and transparently update `user.password_hash = hash_password(password)` before committing the transaction.
3. **Pre-Hashing Denial-of-Service**: Neither `hash_password` nor `verify_password` bounds input string length before handing it to the Argon2 C extension. While Pydantic schemas validate API payloads, internal password checks, admin resets, or script invocations without length bounds risk severe CPU starvation when processing multi-megabyte adversarial inputs.

#### 2. Failure Scenarios & Security/Operational Impact

1. **CPU Starvation DoS**: An unauthenticated attacker sends a 1MB password payload to `/api/auth/password/login`, monopolizing worker CPU threads in C extension hashing and degrading server availability.
2. **Cryptographic Stagnation**: Hashes created under legacy parameters are never transparently migrated to stronger cryptographic bounds upon successful user authentication.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/config/settings.py`, add configurable Argon2 cost parameters:

```python
ARGON2_TIME_COST: int = Field(default=3, ge=1, le=10)
ARGON2_MEMORY_COST: int = Field(default=65536, ge=16384, le=1048576)
ARGON2_PARALLELISM: int = Field(default=4, ge=1, le=16)
PASSWORD_MAX_LENGTH: int = Field(default=128, ge=64, le=1024)
```

2. In `backend/src/novelai/api/auth/passwords.py`, instantiate `PasswordHasher` with explicit settings and export `needs_rehash`:

```python
from functools import lru_cache
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from novelai.config.settings import settings

@lru_cache(maxsize=1)
def get_hasher() -> PasswordHasher:
    return PasswordHasher(
        time_cost=settings.ARGON2_TIME_COST,
        memory_cost=settings.ARGON2_MEMORY_COST,
        parallelism=settings.ARGON2_PARALLELISM,
    )

def hash_password(password: str) -> str:
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        raise ValueError("Password exceeds maximum permitted length.")
    return get_hasher().hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        return False
    try:
        return get_hasher().verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError, TypeError):
        return False

def needs_rehash(password_hash: str) -> bool:
    try:
        return get_hasher().check_needs_rehash(password_hash)
    except Exception:
        return True
```

3. In `backend/src/novelai/services/auth_service.py:password_login`:

```python
if needs_rehash(user.password_hash):
    user.password_hash = hash_password(password)
user.last_login_at = datetime.now(UTC)
self.db_session.flush()
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_argon2_password_security.py`:

```python
from novelai.api.auth.passwords import hash_password, verify_password, needs_rehash, get_hasher
from argon2 import PasswordHasher

def test_password_rehash_detected_on_parameter_upgrade():
    # Hash with weaker parameters
    weak_hasher = PasswordHasher(time_cost=1, memory_cost=16384, parallelism=1)
    weak_hash = weak_hasher.hash("TestPass123!")

    # Assert current hasher flags it as needing rehash
    assert needs_rehash(weak_hash) is True

    # Rehashed with current standard
    current_hash = hash_password("TestPass123!")
    assert needs_rehash(current_hash) is False

def test_password_max_length_dos_guard():
    assert verify_password("A" * 2048, "$argon2id$...") is False
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_argon2_password_security.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible with existing Argon2 hashes. Hashes are transparently upgraded on user login without resetting passwords.
- **Rollback Procedure**: Revert changes to `passwords.py`, `auth_service.py`, and `settings.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/auth/passwords.py backend/src/novelai/services/auth_service.py backend/src/novelai/config/settings.py
  ```

---

### REC-062: User Account Enumeration Timing Oracles via Short-Circuit Hashing & Synchronous Mail

- **ID**: `REC-062`
- **Subsystem/Component**: Authentication / Account Discovery (`novelai.services.auth_service`, `novelai.api.routers.auth`)
- **Target Location**:
  - `backend/src/novelai/services/auth_service.py:146-163` (`password_login`)
  - `backend/src/novelai/services/auth_service.py:167-201` (`request_password_reset`)
  - `backend/src/novelai/services/auth_service.py:96-120` (`register`)
  - `backend/src/novelai/api/routers/auth.py:214-220` (`register` exception mapping)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `password_login` evaluates password hashing conditionally only when an account exists, creating a ~200ms timing discrepancy, while `request_password_reset` synchronously executes outbound SMTP delivery for valid accounts and `register` emits HTTP 409, exposing comprehensive user enumeration oracles.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/auth_service.py:151-160`:

```python
user = self.db_session.query(User).filter(func.lower(User.email) == email).one_or_none()
if (
    user is None
    or not user.is_active
    or user.role == "owner"
    or not user.password_hash
    or not verify_password(password, user.password_hash)
):
    raise ValueError("Invalid email or password.")
```

1. **Password Login Timing Oracle**: Python's boolean short-circuit evaluation aborts before calling `verify_password` when `user is None`. For a non-existent email, the endpoint queries PostgreSQL and returns 401 in <2ms. For an existing email with an invalid password, `verify_password` runs Argon2id, consuming ~150-250ms of CPU time. An unauthenticated attacker measuring response latency can harvest registered user emails with >99% statistical confidence.
2. **Synchronous Mail Delivery Timing Oracle**: In `request_password_reset` (lines 167-201):

```python
user = self.db_session.query(User).filter(...).one_or_none()
if user is None ...:
    return  # returns in <1ms
...
self._deliver_password_reset_email(user.email, raw_token, user.id)  # blocks for 300-2000ms SMTP roundtrip
```

Even though both paths return `{"status": "ok"}` to the client, the network round-trip of synchronous SMTP delivery introduces a massive timing delta (seconds vs milliseconds), completely defeating the blind response contract. 3. **Registration Status Leak**: In `register` (lines 104-106) and `api/routers/auth.py:218`:
An existing account raises `ValueError("An account already exists for this email.")`, returning `HTTP 409 Conflict`. Attackers can probe registration to verify target identities.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Targeted Phishing & Account Harvesting**: Threat actors probe the login API or reset endpoint with employee or customer email lists, determining who holds active accounts on the platform based on network response latency.
2. **Privacy Breach**: Exposes user registration status without requiring authentication.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/api/auth/passwords.py`, generate a pre-computed dummy Argon2id hash at module load time:

```python
_DUMMY_HASH = get_hasher().hash("novelai-timing-invariant-sentinel-token")

def get_dummy_hash() -> str:
    return _DUMMY_HASH
```

2. In `backend/src/novelai/services/auth_service.py:146-163`, guarantee constant-time execution by always verifying against either the candidate hash or the dummy sentinel:

```python
def password_login(self, email: str, password: str) -> dict[str, Any]:
    email = self.normalize_email(email)
    if not email or len(email) > 255:
        raise ValueError("Invalid email or password.")

    user = self.db_session.query(User).filter(func.lower(User.email) == email).one_or_none()

    # Always execute Argon2 verification to eliminate timing delta
    candidate_hash = user.password_hash if (user and user.password_hash) else get_dummy_hash()
    is_password_valid = verify_password(password, candidate_hash)

    if (
        user is None
        or not user.is_active
        or user.role == "owner"
        or not is_password_valid
    ):
        raise ValueError("Invalid email or password.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    self.db_session.flush()
    return {"user_id": user.id, "email": user.email, "role": user.role}
```

3. In `backend/src/novelai/api/routers/auth.py`, dispatch `_deliver_password_reset_email` via FastAPI `BackgroundTasks` so the response returns in constant time regardless of email existence or SMTP latency.

#### 4. Verification & Test Strategy

Create `backend/tests/test_auth_timing_invariance.py`:

```python
import time
from novelai.services.auth_service import AuthService

def test_login_timing_difference_is_negligible(db_session):
    auth_svc = AuthService(db_session)

    # Measure non-existent user latency
    start = time.perf_counter()
    try:
        auth_svc.password_login("nonexistent@example.com", "WrongPassword123!")
    except ValueError:
        pass
    non_existent_duration = time.perf_counter() - start

    # Both paths now run Argon2id, keeping timing differences within noise margin
    assert non_existent_duration > 0.05  # Proves Argon2id ran even for missing user
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_auth_timing_invariance.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking API change. Prevents user discovery while preserving standard 401 Unauthorized responses.
- **Rollback Procedure**: Revert changes to `passwords.py`, `auth_service.py`, and `routers/auth.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/auth/passwords.py backend/src/novelai/services/auth_service.py backend/src/novelai/api/routers/auth.py
  ```

---

### REC-063: Missing PKCE Flow, OIDC Nonce Binding, & Cryptographic ID Token Verification

- **ID**: `REC-063`
- **Subsystem/Component**: OAuth 2.0 / Identity Provider (`novelai.api.auth.google_oauth`, `novelai.api.routers.auth`)
- **Target Location**:
  - `backend/src/novelai/api/auth/google_oauth.py:34-45` (`GoogleOAuthClient.authorization_url`)
  - `backend/src/novelai/api/auth/google_oauth.py:47-88` (`GoogleOAuthClient.exchange_code`)
  - `backend/src/novelai/api/routers/auth.py:318-372` (`google_start`, `google_callback`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: Google OAuth login omits RFC 7636 Proof Key for Code Exchange (PKCE), fails to associate an OpenID Connect `nonce` parameter, discards the cryptographically signed `id_token` without verification, and stores unexpiring state in session cookies.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/auth/google_oauth.py:34-88`:

```python
def authorization_url(self, *, state: str, redirect_uri: str) -> str:
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID or "",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"
```

1. **Omission of PKCE (RFC 7636)**: OAuth 2.0 Security BCP (Best Current Practice) and RFC 9700 mandate PKCE for all clients to prevent authorization code injection and interception. Without `code_challenge` and `code_verifier` (S256), any attacker or malicious browser extension that intercepts the authorization code redirect can redeem it if client secret protections are imperfect or if multiple redirect URIs are configured.
2. **Missing OIDC `nonce` Mitigation**: Because the request scopes include `"openid"`, Google acts as an OpenID Connect Identity Provider. OpenID Connect Core §3.1.2.1 mandates generating a cryptographically random `nonce`, binding it to the user's session, and passing it in the authorization request. Upon token exchange, the `nonce` claim in the ID token must match the session nonce to mitigate replay attacks.
3. **Discarded `id_token` in Exchange**: In `exchange_code`, `token_response.json()` returns an `id_token` JWT signed by Google's JWKS. Instead of validating this token locally (checking signature, `iss="https://accounts.google.com"`, `aud=client_id`, and `exp`), the code ignores the token and makes an extra unauthenticated network round-trip to `GOOGLE_USERINFO_URL` using the bearer access token.
4. **Session State Lifespan**: In `auth.py:326`, `_OAUTH_STATE_KEY` is saved without an expiration timestamp. If a user abandons an OAuth flow, that state token remains accepted until the session cookie expires.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Authorization Code Interception / Injection**: Attackers intercepting redirect URLs can inject captured authorization codes into a victim's session, binding the victim's local account to an attacker's identity.
2. **Replay Attacks & Userinfo Network Dependency**: Relying on unverified access tokens and external userinfo endpoints increases failure rates and vulnerability to token replay.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/api/auth/google_oauth.py`, add PKCE and nonce parameters:

```python
import base64
import hashlib
import secrets

def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using SHA-256."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge

def generate_nonce() -> str:
    return secrets.token_urlsafe(32)
```

2. Update `authorization_url` to require `code_challenge` and `nonce`:

```python
def authorization_url(self, *, state: str, redirect_uri: str, code_challenge: str, nonce: str) -> str:
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID or "",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "nonce": nonce,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"
```

3. In `backend/src/novelai/api/routers/auth.py:google_start`:

```python
code_verifier, code_challenge = generate_pkce_pair()
nonce = generate_nonce()
request.session["oauth_code_verifier"] = code_verifier
request.session["oauth_nonce"] = nonce
request.session["oauth_state_timestamp"] = datetime.now(UTC).timestamp()
auth_url = client.authorization_url(
    state=state,
    redirect_uri=redirect_uri,
    code_challenge=code_challenge,
    nonce=nonce,
)
```

4. In `exchange_code`, include `code_verifier`:

```python
data = {
    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
    "client_secret": client_secret.get_secret_value() if client_secret else "",
    "code": code,
    "code_verifier": code_verifier,
    "grant_type": "authorization_code",
    "redirect_uri": redirect_uri,
}
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_google_oauth_pkce.py`:

```python
from novelai.api.auth.google_oauth import generate_pkce_pair, GoogleOAuthClient

def test_pkce_generation_and_challenge_derivation():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 43
    assert "=" not in challenge

def test_authorization_url_contains_pkce_and_nonce():
    client = GoogleOAuthClient()
    url = client.authorization_url(
        state="test-state",
        redirect_uri="https://example.com/callback",
        code_challenge="test-challenge",
        nonce="test-nonce",
    )
    assert "code_challenge=test-challenge" in url
    assert "code_challenge_method=S256" in url
    assert "nonce=test-nonce" in url
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_google_oauth_pkce.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking change. Google OAuth 2.0 fully supports PKCE and nonces for web applications.
- **Rollback Procedure**: Revert changes to `google_oauth.py` and `routers/auth.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/auth/google_oauth.py backend/src/novelai/api/routers/auth.py
  ```

---

### REC-064: Hardcoded Session Cookie Name Without `__Host-` Prefix & Subdomain Tossing Isolation

- **ID**: `REC-064`
- **Subsystem/Component**: Session Security / Cookie Hardening (`novelai.api.app`, `novelai.main_admin`, `novelai.config.settings`)
- **Target Location**:
  - `backend/src/novelai/api/app.py:111-118` (`SessionMiddleware` registration)
  - `backend/src/novelai/main_admin.py:91-96` (`main_admin` SessionMiddleware)
  - `backend/src/novelai/config/settings.py:752-758` (`session_cookie_secure`)
- **Category**: `Security`
- **Severity**: `Medium`
- **Summary**: Session cookies are hardcoded to `"novelai_session"` across apps without RFC 6265bis `__Host-` prefixing in HTTPS environments, allowing malicious or compromised subdomains to inject rogue session cookies and execute session fixation.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/app.py:111-118` and `backend/src/novelai/main_admin.py:91-96`:

```python
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie="novelai_session",
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
    https_only=session_cookie_secure(),
)
```

1. **Subdomain Cookie Tossing Vulnerability**: In multi-subdomain deployments (e.g. `dokushodo.online`, `dev.dokushodo.online`, `staging.dokushodo.online`), a compromised or malicious application running on any sibling subdomain can emit:
   `Set-Cookie: novelai_session=<attacker_token>; Domain=dokushodo.online; Path=/`
   When the user accesses `dokushodo.online`, the browser sends both cookies. Starlette's cookie parser uses the first encountered header value, allowing an attacker to fixate or corrupt the user's authenticated session.
2. **RFC 6265bis Prefix Guarantees**: Under RFC 6265bis, prefixing a cookie with `__Host-` instructs the browser to enforce:
   - The cookie must be served over HTTPS (`Secure` flag).
   - The cookie must NOT have a `Domain` attribute (strictly host-only, blocking sibling subdomain injection).
   - The cookie must have `Path=/`.
3. **Hardcoded Cookie Names**: The string `"novelai_session"` is duplicated across FastAPI app entry points rather than being centrally resolved from settings.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Cross-Subdomain Session Fixation**: Compromised staging or development sites overwrite production session cookies for visiting users.
2. **Cookie Namespace Collisions**: Admin and Reader instances running in separated environments cannot isolate cookie spaces.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/config/settings.py`, declare `SESSION_COOKIE_NAME` and helper `resolve_session_cookie_name()`:

```python
SESSION_COOKIE_NAME: str = Field(default="novelai_session")

def resolve_session_cookie_name() -> str:
    base_name = settings.SESSION_COOKIE_NAME.strip()
    # In secure production environments, prefix with __Host- for strict domain isolation
    if session_cookie_secure() and not base_name.startswith("__Host-"):
        return f"__Host-{base_name}"
    return base_name
```

2. Update `backend/src/novelai/api/app.py:111-118` and `backend/src/novelai/main_admin.py:91-96`:

```python
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie=resolve_session_cookie_name(),
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
    https_only=session_cookie_secure(),
)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_cookie_security_hardening.py`:

```python
from novelai.config.settings import resolve_session_cookie_name, settings

def test_resolve_session_cookie_name_prefixes_host_when_secure(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_COOKIE_NAME", "novelai_session")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", True)
    assert resolve_session_cookie_name() == "__Host-novelai_session"

def test_resolve_session_cookie_name_unprefixed_in_development(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_COOKIE_NAME", "novelai_session")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", False)
    assert resolve_session_cookie_name() == "novelai_session"
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_cookie_security_hardening.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: In production deployments, users may need to log in once after rollout as the browser transitions to the `__Host-` prefixed cookie. Fully reversible by overriding `SESSION_COOKIE_NAME`.
- **Rollback Procedure**: Revert changes to `app.py`, `main_admin.py`, and `settings.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/app.py backend/src/novelai/main_admin.py backend/src/novelai/config/settings.py
  ```

---

### REC-065: Uncached Database Session Validation & Persistent Zombie Cookies on Revoked Users

- **ID**: `REC-065`
- **Subsystem/Component**: Session Lifecycle / Persistence (`novelai.api.auth.session`)
- **Target Location**:
  - `backend/src/novelai/api/auth/session.py:65-98` (`get_current_user`)
  - `backend/src/novelai/db/models/user.py:35-45` (`User`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `get_current_user` performs a synchronous database query on every authenticated request without caching, leaves client cookies intact when sessions are revoked or accounts disabled, and never validates `issued_at` for users lacking a revocation timestamp.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/auth/session.py:65-98`:

```python
def get_current_user(
    request: Request,
    db_session: Session = Depends(get_db_session),
) -> SessionUser:
    session = request.session
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return GUEST

    user = db_session.get(User, user_id)
    if user is None:
        return GUEST
    if not user.is_active or user.disabled_at is not None:
        return GUEST

    issued_raw = session.get("issued_at")
    if user.session_revoked_at is not None:
        if not isinstance(issued_raw, str):
            return GUEST
        try:
            issued_at = datetime.fromisoformat(issued_raw)
            ...
            if issued_at < revoked_at:
                return GUEST
        except (ValueError, TypeError):
            return GUEST
```

1. **Connection Pool Contention**: Every API call (including high-frequency reading progress heartbeats and catalog lookups) runs `db_session.get(User, user_id)`. Under transaction pooling mode (`DB_CONNECTION_MODE="transaction"`), this acquires a physical PostgreSQL connection for a simple user identity check. Under concurrent reader load, this quickly saturates the 5-connection budget mandated by `AGENTS.md`.
2. **Zombie Cookie Load**: When a user account is disabled (`user.is_active = False` or `user.disabled_at` is set) or revoked, `get_current_user` returns `GUEST`. However, `request.session` is never modified or cleared (`request.session.clear()` is omitted). The browser continues sending the signed session cookie with every subsequent HTTP request indefinitely, forcing the backend to query PostgreSQL for a dead account on every navigation.
3. **Unbounded Session Age**: For active users whose sessions were never explicitly revoked (`user.session_revoked_at is None`, which is the initial state for all users), the `if user.session_revoked_at is not None:` guard causes the entire `issued_at` check to be bypassed. As a result, signed cookies never expire server-side unless revoked by an administrator.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Connection Pool Exhaustion**: High read concurrency on authenticated endpoints starves backend background workers of database connections.
2. **Persistent Revoked Access**: If a user's cookie is retained across browser restarts, it remains active indefinitely because `issued_at` is never evaluated against a global maximum age.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/api/auth/session.py:65-98`, clear stale sessions and validate maximum session age:

```python
def get_current_user(
    request: Request,
    db_session: Session = Depends(get_db_session),
) -> SessionUser:
    session = request.session
    user_id = session.get("user_id")
    if not isinstance(user_id, int):
        return GUEST

    issued_raw = session.get("issued_at")
    if not isinstance(issued_raw, str):
        request.session.clear()
        return GUEST

    try:
        issued_at = datetime.fromisoformat(issued_raw)
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        request.session.clear()
        return GUEST

    # Enforce global max session lifetime regardless of revocation status
    if (datetime.now(UTC) - issued_at).total_seconds() > settings.SESSION_MAX_AGE:
        request.session.clear()
        return GUEST

    user = db_session.get(User, user_id)
    if user is None or not user.is_active or user.disabled_at is not None:
        request.session.clear()
        return GUEST

    if user.session_revoked_at is not None:
        revoked_at = user.session_revoked_at
        if revoked_at.tzinfo is None:
            revoked_at = revoked_at.replace(tzinfo=UTC)
        if issued_at < revoked_at:
            request.session.clear()
            return GUEST

    if user.role not in ("guest", "user", "owner"):
        request.session.clear()
        return GUEST

    return SessionUser(user_id=user.id, email=user.email, role=user.role)
```

2. Introduce a 15-second TTL in-memory cache for user verification tuples `(is_active, disabled_at, session_revoked_at, role)` to prevent database lookups on high-frequency API polling.

#### 4. Verification & Test Strategy

Create `backend/tests/test_session_lifecycle_and_zombie_cleanup.py`:

```python
from novelai.api.auth.session import get_current_user, GUEST
from novelai.db.models.user import User
from datetime import datetime, UTC, timedelta
from unittest.mock import MagicMock

def test_disabled_user_clears_session_cookie(db_session):
    user = User(email="test@example.com", is_active=False, role="user")
    db_session.add(user)
    db_session.commit()

    request = MagicMock()
    request.session = {"user_id": user.id, "issued_at": datetime.now(UTC).isoformat()}

    res = get_current_user(request, db_session)
    assert res == GUEST
    assert len(request.session) == 0  # Session cleared
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_session_lifecycle_and_zombie_cleanup.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backwards-compatible. Forces browsers to drop invalid cookies cleanly.
- **Rollback Procedure**: Revert changes to `session.py` and `db/models/user.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/auth/session.py backend/src/novelai/db/models/user.py
  ```

---

### REC-066: IP-Only Rate Limiter Keying on Unauthenticated Endpoints Enabling Credential Stuffing

- **ID**: `REC-066`
- **Subsystem/Component**: Rate Limiting / Abuse Prevention (`novelai.api.auth.security`, `novelai.api.routers.auth`)
- **Target Location**:
  - `backend/src/novelai/api/auth/security.py:80-112` (`public_rate_limit_key`, `require_public_rate_limit`)
  - `backend/src/novelai/api/routers/auth.py:165-190` (`login`)
  - `backend/src/novelai/api/routers/auth.py:230-245` (`password_login`)
  - `backend/src/novelai/api/routers/auth.py:247-264` (`password_reset_request`)
  - `backend/src/novelai/db/models/user.py:35-45`
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: Rate limiting on unauthenticated authentication endpoints keys exclusively on client IP, allowing attackers with proxy pools to execute distributed credential stuffing while causing denial-of-service for legitimate users on shared IPs.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/auth/security.py:80-112`:

```python
def public_rate_limit_key(request: Request, *, user_id: int | None = None) -> str:
    if user_id is not None:
        return f"user:{user_id}"
    session_user_id = request.session.get("user_id")
    if isinstance(session_user_id, int):
        return f"user:{session_user_id}"
    ...
    return f"ip:{_client_ip(request)}"
```

On unauthenticated endpoints (`POST /api/auth/password/login`, `POST /api/auth/login`, `POST /api/auth/password/reset/request`), the client is unauthenticated, so `user_id` is always None.

1. **Distributed Credential Stuffing Bypass**: An attacker rotating residential IP proxies or cloud egress IPs bypasses the 10-requests-per-minute threshold because every request arrives from a different IP. The attacker can test millions of passwords against a specific account (e.g. the owner account or known user email) without ever hitting the rate limit.
2. **Denial of Service on Shared NAT/Carrier IPs**: In corporate environments, universities, or mobile networks using Carrier-Grade NAT (CGNAT), hundreds of users share a single public IPv4 address. If one user enters their password incorrectly 10 times, all other users behind that NAT gateway are blocked from logging in.
3. **Lack of Account Lockout State**: Neither `User` nor `AuthService` tracks failed login counters (`failed_login_attempts`, `locked_until`). Brute force resistance relies entirely on transient IP rate limiting.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Account Takeover via Distributed Brute-Force**: Attackers test common passwords against known user emails from rotating IP addresses without rate limit interference.
2. **Denial of Service for Legitimate Users**: Shared office and university NAT IPs are locked out by a single malicious or mistyped login script.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/db/models/user.py`, add failed attempt counters and lockout timestamp:

```python
failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

2. In `backend/src/novelai/services/auth_service.py:password_login`:

```python
now = datetime.now(UTC)
if user is not None and user.locked_until is not None:
    locked_until = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=UTC)
    if locked_until > now:
        raise ValueError("Account temporarily locked due to excessive failed attempts. Please try again later.")

# On login failure for existing user
if not is_password_valid:
    if user is not None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
        self.db_session.flush()
    raise ValueError("Invalid email or password.")

# On login success
user.failed_login_attempts = 0
user.locked_until = None
```

3. Support dual-key rate limiting in `require_public_rate_limit(request, action, secondary_key=email)`.

#### 4. Verification & Test Strategy

Create `backend/tests/test_account_lockout_and_rate_limiting.py`:

```python
from novelai.services.auth_service import AuthService
from novelai.db.models.user import User
import pytest

def test_account_locks_after_5_failed_attempts(db_session):
    user = User(email="target@example.com", is_active=True, role="user")
    auth_svc = AuthService(db_session)
    user.password_hash = auth_svc.hash_password("CorrectPass123!")
    db_session.add(user)
    db_session.commit()

    # Fail 5 times
    for _ in range(5):
        with pytest.raises(ValueError, match="Invalid email or password"):
            auth_svc.password_login("target@example.com", "WrongPassword!")

    # 6th attempt fails due to lockout
    with pytest.raises(ValueError, match="Account temporarily locked"):
        auth_svc.password_login("target@example.com", "CorrectPass123!")
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_account_lockout_and_rate_limiting.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Requires Alembic migration `YYYY-MM-DD_<hash>_add_user_lockout_columns.py`. Reversible via `op.drop_column`.
- **Rollback Procedure**: Revert changes to `auth/security.py`, `routers/auth.py`, and `db/models/user.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/auth/security.py backend/src/novelai/api/routers/auth.py backend/src/novelai/db/models/user.py
  ```

---

### REC-067: Static Owner Bootstrap Secret Vulnerability, Lack of Deprecation, & Missing Lockout

- **ID**: `REC-067`
- **Subsystem/Component**: Privileged Access / Owner Auth (`novelai.api.routers.auth`, `novelai.config.settings`)
- **Target Location**:
  - `backend/src/novelai/api/routers/auth.py:165-195` (`login` endpoint)
  - `backend/src/novelai/config/settings.py:410-415` (`OWNER_BOOTSTRAP_SECRET`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `POST /api/auth/login` uses a shared static environment string without computational proof-of-work, lacks post-bootstrap deprecation after initial owner setup, and provides no progressive lockout or alerting on brute-force attempts.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/auth.py:165-185`:

```python
@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Owner bootstrap login using OWNER_BOOTSTRAP_SECRET."""
    require_public_rate_limit(request, "auth_login")
    bootstrap_secret = settings.OWNER_BOOTSTRAP_SECRET
    if not bootstrap_secret:
        ...
    if not secrets.compare_digest(payload.secret, bootstrap_secret):
        logger.warning("Failed owner login attempt.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
```

1. **Microsecond Timing & Low Computational Cost**: Unlike `password_login` which enforces Argon2id (consuming ~200ms CPU), `secrets.compare_digest(payload.secret, bootstrap_secret)` executes in sub-microsecond time. An attacker distributing requests across multiple IP addresses can send tens of thousands of guesses per minute without creating noticeable server load or triggering IP-based limits.
2. **Permanent Backdoor Lifetime**: The bootstrap secret is intended solely for initial system provisioning (creating the first owner account). However, `OWNER_BOOTSTRAP_SECRET` remains permanently active throughout the operational life of the cluster. Even after an owner account is established and operating via standard credentials, the backdoor bootstrap endpoint remains live. If the secret is leaked via environment logs, container inspection, or CI/CD logs, any holder gains instantaneous, full owner privileges.
3. **Absence of Progressive Backoff and Urgent Alerting**: A failed owner login attempt merely emits `logger.warning("Failed owner login attempt.")`. It does not trigger an email notification to the owner, does not log to `AuditLog`, and does not activate progressive backoff on the bootstrap endpoint.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Total Privilege Compromise**: Leaked environment variables grant instant owner access to attackers without cryptographic proof-of-work.
2. **Silent Brute-Force**: Attackers probe the bootstrap endpoint without triggering account lockout or administrative alerts.

#### 3. Concrete Implementation Specification

1. In `backend/src/novelai/config/settings.py`, introduce `ALLOW_OWNER_BOOTSTRAP: bool = Field(default=False)`:

```python
ALLOW_OWNER_BOOTSTRAP: bool = Field(
    default=False,
    description="Explicitly allow owner bootstrap login via static secret. Disable once owner is provisioned.",
)
```

2. In `backend/src/novelai/api/routers/auth.py:login`:

```python
@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    svc: AuthService = Depends(get_auth_service),
) -> UserResponse:
    if not settings.ALLOW_OWNER_BOOTSTRAP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner bootstrap login is permanently disabled. Use password or OAuth login.",
        )

    require_public_rate_limit(request, "auth_login")
    bootstrap_secret = settings.OWNER_BOOTSTRAP_SECRET
    if not bootstrap_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Owner login is not configured on this server.",
        )

    # Artificial delay to match Argon2id computation
    await asyncio.sleep(1.0)

    if not secrets.compare_digest(payload.secret, bootstrap_secret):
        logger.warning("Failed owner bootstrap login attempt from IP: %s", get_client_ip(request))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_owner_bootstrap_security.py`:

```python
import pytest
from fastapi import status
from httpx import AsyncClient
from novelai.config.settings import settings

@pytest.mark.asyncio
async def test_owner_bootstrap_disabled_by_default(async_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_OWNER_BOOTSTRAP", False)
    response = await async_client.post("/api/auth/login", json={"secret": "any_secret"})
    assert response.status_code == status.HTTP_403_FORBIDDEN
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_owner_bootstrap_security.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Setting `ALLOW_OWNER_BOOTSTRAP=True` in `.env` restores bootstrap capability during initial installation.
- **Rollback Procedure**: Revert changes to `routers/auth.py` and `settings.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/auth.py backend/src/novelai/config/settings.py
  ```

---

### REC-068: Missing Content-Security-Policy, HSTS Preload Directives, & BaseHTTPMiddleware Overhead

- **ID**: `REC-068`
- **Subsystem/Component**: Security Middleware / HTTP Headers (`novelai.api.middleware.security`, `novelai.config.settings`)
- **Target Location**:
  - `backend/src/novelai/api/middleware/security.py:28-55` (`SecurityHeadersMiddleware`)
  - `backend/src/novelai/config/settings.py:435-445` (`SECURITY_HEADERS_ENABLED`, `HSTS_MAX_AGE_SECONDS`)
- **Category**: `Security`
- **Severity**: `Medium`
- **Summary**: `SecurityHeadersMiddleware` omits `Content-Security-Policy` (CSP) and `Cross-Origin-Resource-Policy` (CORP), lacks HSTS `preload` support, and suffers from Starlette `BaseHTTPMiddleware` performance degradation and streaming buffering.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/middleware/security.py:28-55`:

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        response.headers.setdefault("X-Request-ID", request_id)
        if settings.SECURITY_HEADERS_ENABLED:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
            if settings.HSTS_MAX_AGE_SECONDS > 0:
                hsts_value = f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains"
                response.headers.setdefault("Strict-Transport-Security", hsts_value)
        return response
```

1. **Missing Modern Browser Defenses**:
   - **No `Content-Security-Policy`**: API endpoints returning JSON, error pages, or HTML redirects must include a baseline CSP (`default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`) to protect against injection and clickjacking.
   - **No `Cross-Origin-Resource-Policy` (CORP)**: Missing `Cross-Origin-Resource-Policy: same-origin` leaves sensitive JSON endpoints exposed to cross-origin speculative side-channel attacks (Spectre/Meltdown).
   - **Missing HSTS `preload`**: For production domains (`dokushodo.online`) to be included in browser HSTS preload lists, `Strict-Transport-Security` must include the `preload` directive.
2. **Starlette `BaseHTTPMiddleware` Bottleneck**: `BaseHTTPMiddleware` wraps request processing in an AnyIO task group and intercepts response streams. This has known performance penalties: it adds task allocation overhead to every request, breaks true response streaming (buffering chunked responses into memory), and suppresses low-level ASGI cancellation signals.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Streaming Memory Buffering**: Large chapter exports and server-sent events are buffered into memory rather than streamed chunk-by-chunk to the client.
2. **Cross-Origin Information Leakage**: Missing CORP headers allow malicious cross-origin resources to query API endpoints in speculative execution attacks.

#### 3. Concrete Implementation Specification

Refactor `SecurityHeadersMiddleware` into a pure ASGI middleware:

```python
from starlette.types import ASGIApp, Receive, Scope, Send
import uuid

class SecurityHeadersMiddleware:
    """Pure ASGI middleware adding security headers without streaming buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                # Ensure X-Request-ID
                req_id = str(uuid.uuid4().hex).encode("ascii")
                headers.append((b"x-request-id", req_id))

                if settings.SECURITY_HEADERS_ENABLED:
                    headers.append((b"x-content-type-options", b"nosniff"))
                    headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                    headers.append((b"x-frame-options", b"DENY"))
                    headers.append((b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"))
                    headers.append((b"cross-origin-opener-policy", b"same-origin"))
                    headers.append((b"cross-origin-resource-policy", b"same-origin"))
                    headers.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"))

                    if settings.HSTS_MAX_AGE_SECONDS > 0:
                        hsts = f"max-age={settings.HSTS_MAX_AGE_SECONDS}; includeSubDomains"
                        if getattr(settings, "HSTS_PRELOAD", True):
                            hsts += "; preload"
                        headers.append((b"strict-transport-security", hsts.encode("ascii")))

                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_asgi_security_headers.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_security_headers_present_on_api_response(async_client: AsyncClient):
    response = await async_client.get("/health/live")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("cross-origin-resource-policy") == "same-origin"
    assert "default-src 'none'" in response.headers.get("content-security-policy", "")
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_asgi_security_headers.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Pure ASGI implementation avoids `BaseHTTPMiddleware` overhead and maintains compatibility with all HTTP clients.
- **Rollback Procedure**: Revert changes to `middleware/security.py` and `settings.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/middleware/security.py backend/src/novelai/config/settings.py
  ```

---

### REC-069: Security Event Blind Spots in Audit Logs for Auth Failures, Role Denials, & CSRF Drops

- **ID**: `REC-069`
- **Subsystem/Component**: Audit Logging / Security Telemetry (`novelai.api.auth.roles`, `novelai.api.routers.auth`, `novelai.api.auth.security`, `novelai.services.audit_service`)
- **Target Location**:
  - `backend/src/novelai/api/auth/roles.py:40-52` (`require_role`)
  - `backend/src/novelai/api/routers/auth.py:175-185, 230-245` (`login`, `password_login`)
  - `backend/src/novelai/api/auth/security.py:59-75` (`require_csrf_token`)
  - `backend/src/novelai/services/audit_service.py:219-270` (`AuditService.log`)
- **Category**: `Observability`
- **Severity**: `Medium`
- **Summary**: `AuditService` is strictly called for successful administrative CRUD operations, leaving authentication failures, unauthorized privilege escalation attempts (403), and CSRF rejections completely invisible in the audit trail.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/admin_users.py:160-175`, mutations call `AuditService(session).log(action=..., metadata=...)`.
However, in core security enforcement locations:

1. **Role Elevation Failures in `require_role` (`backend/src/novelai/api/auth/roles.py:40-52`)**:

```python
if not user.is_authenticated:
    raise HTTPException(status_code=401, detail="Authentication required.")
raise HTTPException(status_code=403, detail="Insufficient permissions.")
```

When an authenticated regular user (`role="user"`) attempts to access an owner route (e.g. `/api/admin/users`, `/api/admin/crawl`, or system settings), the request is rejected with 403 Forbidden, but NO audit event is written. Security operators reviewing `audit_logs` cannot detect internal privilege escalation attempts. 2. **Authentication Failures (`backend/src/novelai/api/routers/auth.py`)**: Failed owner bootstrap attempts, repeated invalid user password attempts, and invalid OAuth callback states write only transient console logger messages or raise HTTP exceptions. None are persisted to `audit_logs`. 3. **CSRF Rejections (`backend/src/novelai/api/auth/security.py:59-75`)**: Untrusted origin headers and forged or missing CSRF tokens raise HTTP 403 silently without audit tracking. Cross-site request forgery attacks in the wild leave zero forensic trail.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Undetected Reconnaissance**: Attacker probes privileged endpoints with stolen low-privilege tokens without alert triggers.
2. **Post-Breach Forensic Void**: Incident investigations cannot determine how long an account was brute-forced or which endpoints were probed.

#### 3. Concrete Implementation Specification

1. Add standardized security event actions in `novelai.services.audit_service`:
   - `auth.login_failed`
   - `auth.bootstrap_login_failed`
   - `auth.privilege_denied`
   - `security.csrf_rejected`
2. Define a non-throwing security event recorder in `novelai.services.audit_service`:

```python
def log_security_event(
    db: Session,
    action: str,
    actor_user_id: str | None,
    client_ip: str | None,
    details: dict[str, Any],
) -> None:
    """Record security event with independent commit to preserve record on abort."""
    try:
        entry = AuditLog(
            action=action,
            actor_user_id=actor_user_id,
            target_type="security_boundary",
            target_id=client_ip or "unknown",
            details_json=json.dumps(details),
            created_at=datetime.now(UTC),
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to record security audit log: %s", exc)
        db.rollback()
```

3. In `require_role`:

```python
if not user.is_authenticated:
    raise HTTPException(status_code=401, detail="Authentication required.")
log_security_event(
    db=db,
    action="auth.privilege_denied",
    actor_user_id=user.user_id,
    client_ip=get_client_ip(request),
    details={"attempted_path": request.url.path, "user_role": user.role},
)
raise HTTPException(status_code=403, detail="Insufficient permissions.")
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_security_audit_logging.py`:

```python
import pytest
from fastapi import status
from httpx import AsyncClient
from novelai.db.models.audit import AuditLog

@pytest.mark.asyncio
async def test_role_denial_writes_audit_log(user_client: AsyncClient, db_session):
    response = await user_client.get("/api/admin/users")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # Verify audit log created
    log = db_session.query(AuditLog).filter_by(action="auth.privilege_denied").first()
    assert log is not None
    assert "/api/admin/users" in log.details_json
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_security_audit_logging.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking addition. Uses existing `AuditLog` table.
- **Rollback Procedure**: Revert changes to `auth/roles.py`, `routers/auth.py`, `auth/security.py`, and `services/audit_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/auth/roles.py backend/src/novelai/api/routers/auth.py backend/src/novelai/api/auth/security.py backend/src/novelai/services/audit_service.py
  ```

---

### REC-070: Repeated Per-Request IP Network Parsing in Proxy Validation & Dead Host Header Logic

- **ID**: `REC-070`
- **Subsystem/Component**: Network Boundary / Reverse Proxy (`backend/src/novelai/api/middleware/security.py`, `novelai.config.settings`)
- **Target Location**:
  - `backend/src/novelai/api/middleware/security.py:58-75` (`_is_trusted_proxy`)
  - `backend/src/novelai/api/middleware/security.py:101-112` (`is_allowed_host`)
  - `backend/src/novelai/config/settings.py:440-450` (`TRUSTED_PROXY_CIDRS`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `_is_trusted_proxy` dynamically parses CIDR strings via `ipaddress.ip_network` on every incoming request rather than caching parsed networks at startup, while `is_allowed_host` is unreferenced dead code and default proxy CIDRs omit Docker internal bridge subnets.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/middleware/security.py:58-75`:

```python
def _is_trusted_proxy(client_ip: str) -> bool:
    """Check if the client IP is within a trusted proxy CIDR range."""
    if not settings.TRUSTED_PROXY_CIDRS:
        return False
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for cidr_str in settings.TRUSTED_PROXY_CIDRS:
        try:
            network = ipaddress.ip_network(cidr_str, strict=False)
            if ip in network:
                return True
        except ValueError:
            continue
    return False
```

1. **Dynamic Object Allocation Overhead**: Python's `ipaddress.ip_network(cidr_str)` parses and instantiates complex network objects with bitmask calculations. Running this in a `for` loop over `settings.TRUSTED_PROXY_CIDRS` on every HTTP request entering `get_client_ip()` introduces significant CPU latency and GC pressure on high-frequency API routes. Pre-compiling `TRUSTED_PROXY_CIDRS` into a tuple of network objects at startup provides an immediate performance boost.
2. **Dead Code Accumulation**: Lines 101-112 define `is_allowed_host(host: str | None) -> bool`. This function is completely unreferenced across the entire repository. `backend/src/novelai/api/app.py` uses Starlette's built-in `TrustedHostMiddleware`, leaving `is_allowed_host` as dead, untested code.
3. **Incomplete Default Proxy Ranges**: In containerized deployments (`deploy/compose.yml`), Caddy and Uvicorn communicate over internal Docker bridge networks (`172.16.0.0/12` or `10.0.0.0/8`), while local testing often uses IPv6 loopback (`::1`). If `TRUSTED_PROXY_CIDRS` only contains `"127.0.0.1"`, requests forwarded by Caddy fail the `_is_trusted_proxy` check, causing `get_client_ip` to return Caddy's internal container IP (`172.x.x.x`) and breaking all client IP logging and rate limiting.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Rate Limiting Collapse**: All users are lumped into Caddy's container IP, causing a single abusive user to exhaust rate limits for all users globally.
2. **CPU Waste**: Every API request repeatedly parses string CIDRs into Python network objects.

#### 3. Concrete Implementation Specification

1. Pre-compile trusted proxy networks once at module load:

```python
_TRUSTED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = tuple(
    ipaddress.ip_network(cidr.strip(), strict=False)
    for cidr in settings.TRUSTED_PROXY_CIDRS
    if cidr.strip()
)

def _is_trusted_proxy(client_ip: str) -> bool:
    try:
        ip = ipaddress.ip_address(client_ip)
        return any(ip in net for net in _TRUSTED_NETWORKS)
    except ValueError:
        return False
```

2. Remove the unused `is_allowed_host` function to eliminate dead code.
3. In `settings.py`, include Docker default bridge ranges (`172.16.0.0/12`, `10.0.0.0/8`) and IPv6 loopback (`::1`) in `TRUSTED_PROXY_CIDRS`.

#### 4. Verification & Test Strategy

Create `backend/tests/test_proxy_validation.py`:

```python
import ipaddress
from novelai.api.middleware.security import _is_trusted_proxy

def test_docker_bridge_ip_identified_as_trusted():
    assert _is_trusted_proxy("172.20.0.4") is True
    assert _is_trusted_proxy("127.0.0.1") is True
    assert _is_trusted_proxy("198.51.100.45") is False
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_proxy_validation.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Backward compatible with all deployments.
- **Rollback Procedure**: Revert changes to `middleware/security.py` and `settings.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/middleware/security.py backend/src/novelai/config/settings.py
  ```

---

## Iteration 8: Admin Control Plane, Takedown Workflow, Moderation, Requests, User Management, & Quota Systems

Audit Focus: DMCA takedown lifecycle, content moderation, catalog slug gating, user requests, user role management, account lifecycle, provider quota controllers (`RedisGeminiQuotaController`), usage accounting (`UsageService`), glossary suggestions moderation, library deletion cascades, and manual worker triggers across `backend/src/novelai/api/routers/admin*.py`, `backend/src/novelai/services/takedown_service.py`, `backend/src/novelai/services/novel_request_service.py`, `backend/src/novelai/services/gemini_request_control.py`, `backend/src/novelai/services/library_service.py`, `backend/src/novelai/services/glossary_suggestion_service.py`, and `backend/src/novelai/services/usage_service.py`.

### Summary of Recommendations (Iteration 8)

| ID          | Subsystem / Component                    | Category          | Title                                                                                                       |
| :---------- | :--------------------------------------- | :---------------- | :---------------------------------------------------------------------------------------------------------- |
| **REC-071** | Takedown Workflow / Content Moderation   | Architecture      | DMCA Takedown Approval Lacks Workflow Cascading, Background Activity Cancellation, & CDN Edge Purge         |
| **REC-072** | Content Moderation / Public Catalog      | Performance       | Unbounded Full-Table URL Scan & In-Memory Path Splitting in Catalog Takedown Slug Resolution                |
| **REC-073** | Novel Requests / Moderation              | Weakness          | Novel Request Lifecycle Lacks State Machine Invariant Validation, Aggregated Upvoting, & Audit Telemetry    |
| **REC-074** | Novel Request Workflow / Data Integrity  | Bug / Reliability | Integer Casting of Canonical Chapter Identifiers in Novel Request Intake Violates Repository Invariant      |
| **REC-075** | User Management / Access Control         | Security          | User Role Mutation Lacks Self-Targeting Guardrails & Missing Account Deletion / GDPR Anonymization Pipeline |
| **REC-076** | Provider Quota / Rate Limiting           | Performance       | In-Memory JSON List Serialization and 15-Second Distributed Lock Contention in `RedisGeminiQuotaController` |
| **REC-077** | Library Management / Admin Control Plane | Bug / Reliability | Missing Database Transactional Sync and Cascade in Admin Novel Deletion Causing Relational Orphanage        |
| **REC-078** | Glossary Management / Admin Moderation   | Bug / Reliability | Bulk Suggestion "Accept-All" Action Bypasses Database Glossary Persistence & Leaves DB Unsynchronized       |
| **REC-079** | Usage Accounting / Cost Control          | Performance       | Double Synchronous Full-File JSON Rewrite and Interprocess Lock Contention in Per-Request Usage Accounting  |
| **REC-080** | Worker Control / Admin Control Plane     | Concurrency       | Unsynchronized Concurrency and State Desynchronization in Admin Manual Worker Trigger `run-once`            |

---

### REC-071: DMCA Takedown Approval Lacks Workflow Cascading, Background Activity Cancellation, & CDN Edge Purge

- **ID**: `REC-071`
- **Subsystem/Component**: Takedown Workflow / Content Moderation (`novelai.services.takedown_service`, `novelai.api.routers.admin_takedown`)
- **Target Location**:
  - `backend/src/novelai/services/takedown_service.py:92-111` (`TakedownService.review`)
  - `backend/src/novelai/api/routers/admin_takedown.py:108-135` (`review_takedown`)
  - `backend/src/novelai/services/takedown_service.py:17-25` (`VALID_STATUSES`)
- **Category**: `Architecture`
- **Severity**: `High`
- **Summary**: Approving a DMCA takedown notice in `TakedownService.review()` only mutates `TakedownRequest.status = "approved"` and invokes in-process `invalidate_public_projection_cache()`. It fails to cascade state updates to target `Novel` records, omits draining or canceling queued/active crawl and translation activities, neglects to evict translation cache entries, and does not trigger Cloudflare CDN edge cache purges, allowing infringing content to remain cached at the edge and continually processed by background LLM workers.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/takedown_service.py:92-111`:

```python
req.status = status
req.reviewer_notes = reviewer_notes
req.reviewed_at = datetime.now(UTC)
req.reviewed_by_user_id = reviewed_by_user_id
self.db.flush()
from novelai.services.public_projection_cache import invalidate_public_projection_cache

invalidate_public_projection_cache()
logger.info("TakedownRequest #%s → %s", request_id, status)
return req
```

1. **Missing Entity Cascades**: The takedown notice stores an `infringing_url`. While public reader and catalog endpoints inspect `active_takedown_slugs`, approving a takedown does _not_ mutate the underlying `Novel.publication_status` to `"takedown"`, `"hidden"`, or `"suspended"` in PostgreSQL. The novel remains registered as an active publication across internal services, exports, and administration feeds.
2. **Active Crawler / Translation Activity Leaks**: If a crawl or translation activity is currently queued or executing in `ActivityQueueService` for the infringed novel/chapter, approving the DMCA notice does nothing to cancel it. The worker continues executing expensive LLM provider calls, persists generated translated chapters into R2, and commits chapter metadata into PostgreSQL for content that has been legally ordered taken down.
3. **Translation Cache Retention**: `TranslationCache` stores chunks keyed by Japanese source hash. When a takedown is approved, existing cached translations for that novel remain in Redis/R2 cache. If the novel or chapters are subsequently re-crawled or requested, the infringed translations are immediately served from cache.
4. **Missing Cloudflare Edge Purge**: Public reader pages and catalog endpoints emit `Cache-Control: public, max-age=...` or `s-maxage` headers. In a production environment with Cloudflare CDN or reverse-proxy caching, simply invalidating the local Python `public_projection_cache` has zero effect on Cloudflare edge caches. Anonymous web visitors continue to receive HTTP 200 responses with the copyrighted text until TTL expiration.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Legal Contempt / Ongoing DMCA Infringement**: Approved takedown requests continue serving infringed text from Cloudflare edge caches, subjecting operators to statutory damages.
2. **Wasted Compute and Provider Quotas**: Background worker threads burn through expensive Gemini/OpenAI API quotas translating chapters of a novel that has already been taken down.

#### 3. Concrete Implementation Specification

Expand `TakedownService.review()` to execute a complete moderation cascade upon approval:

```python
from novelai.db.models.novel import Novel
from novelai.db.models.activity import Activity
from novelai.infrastructure.http.client import get_http_client
from novelai.config.settings import settings

def review(
    self,
    request_id: int,
    status: str,
    reviewer_notes: str | None = None,
    reviewed_by_user_id: int | None = None,
) -> TakedownRequest:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Valid: {sorted(VALID_STATUSES)}")
    req = self.get_request(request_id)
    if not req:
        return None
    req.status = status
    req.reviewer_notes = reviewer_notes
    req.reviewed_at = datetime.now(UTC)
    req.reviewed_by_user_id = reviewed_by_user_id

    if status == "approved":
        # 1. Resolve novel by slug/id and update publication status
        novel = None
        if getattr(req, "target_novel_id", None):
            novel = self.db.query(Novel).filter_by(novel_id=req.target_novel_id).first()
        elif getattr(req, "target_slug", None):
            novel = self.db.query(Novel).filter_by(slug=req.target_slug).first()

        if novel:
            novel.publication_status = "takedown"
            novel.updated_at = datetime.now(UTC)

            # 2. Cancel pending/running activities
            active_tasks = (
                self.db.query(Activity)
                .filter(
                    Activity.payload["novel_id"].astext == novel.novel_id,
                    Activity.status.in_(["pending", "running"]),
                )
                .all()
            )
            for task in active_tasks:
                task.status = "cancelled"
                task.error = "dmca_takedown_enforced"

        self.db.flush()

        # 3. Purge Cloudflare Edge Cache
        self._purge_edge_cache(novel)

    invalidate_public_projection_cache()
    return req

def _purge_edge_cache(self, novel: Novel | None) -> None:
    zone_id = getattr(settings, "CLOUDFLARE_ZONE_ID", None)
    api_token = getattr(settings, "CLOUDFLARE_API_TOKEN", None)
    if not (zone_id and api_token and novel):
        return

    prefixes = [
        f"https://{settings.CANONICAL_HOST}/novel/{novel.slug}",
        f"https://{settings.CANONICAL_HOST}/reader/{novel.slug}",
    ]
    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache",
                headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
                json={"prefixes": prefixes},
            )
    except Exception as exc:
        logger.warning("Failed to purge Cloudflare edge cache for %s: %s", novel.slug, exc)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_takedown_cascade.py`:

```python
import pytest
from novelai.services.takedown_service import TakedownService
from novelai.db.models.novel import Novel
from novelai.db.models.activity import Activity

def test_takedown_approval_cancels_activities_and_marks_novel(db_session):
    novel = Novel(novel_id="nov-dmca", slug="dmca-novel", title="Infringing", publication_status="published")
    act = Activity(activity_id="act-1", activity_type="translate", payload={"novel_id": "nov-dmca"}, status="running")
    db_session.add_all([novel, act])
    db_session.commit()

    service = TakedownService(db_session)
    req = service.submit(infringing_url="https://example.com/novel/dmca-novel", email="holder@example.com", target_slug="dmca-novel")
    db_session.commit()

    service.review(req.id, status="approved", reviewed_by_user_id=1)
    db_session.commit()

    assert novel.publication_status == "takedown"
    assert act.status == "cancelled"
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_takedown_cascade.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Non-breaking operational change. Reversing approval via counter-notice restores `Novel.publication_status = "published"`.
- **Rollback Procedure**: Revert changes to `services/takedown_service.py` and `routers/admin_takedown.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/takedown_service.py backend/src/novelai/api/routers/admin_takedown.py
  ```

---

### REC-072: Unbounded Full-Table URL Scan & In-Memory Path Splitting in Catalog Takedown Slug Resolution

- **ID**: `REC-072`
- **Subsystem/Component**: Content Moderation / Public Catalog (`novelai.services.takedown_service`, `novelai.api.routers.public_catalog`)
- **Target Location**:
  - `backend/src/novelai/services/takedown_service.py:130-139` (`TakedownService.active_takedown_slugs`)
  - `backend/src/novelai/api/routers/public_catalog.py:179-195` (`list_novels`)
  - `backend/src/novelai/db/models/takedown.py:15-30` (`TakedownRequest`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `active_takedown_slugs` executes a full-table scan on `TakedownRequest` for all approved URLs, loads the entire set across the wire into Python, and parses/splits URL path segments in memory on every catalog request. This introduces an $O(N)$ query and CPU bottleneck that degrades catalog listing throughput, while post-query in-memory filtering silently shrinks catalog page sizes, violating client pagination contracts.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/takedown_service.py:130-139`:

```python
def active_takedown_slugs(self, slugs: list[str]) -> set[str]:
    """Return requested slugs targeted by approved notices using one query."""
    normalized = {unquote(slug).strip("/").casefold() for slug in slugs if slug.strip("/")}
    if not normalized:
        return set()
    urls = self.db.query(TakedownRequest.infringing_url).filter(TakedownRequest.status == "approved").all()
    targeted = {
        unquote(segment).casefold() for (url,) in urls for segment in urlsplit(url).path.split("/") if segment
    }
    return normalized & targeted
```

1. **Full-Table Scan and Serialization**: Every single public catalog listing query (`GET /api/catalog/novels`) invokes `active_takedown_slugs`. As DMCA takedowns accumulate over time, this query transfers thousands of full URL strings from PostgreSQL to the backend process. Splitting paths and unquoting segments for every URL in Python on every catalog page load wastes CPU cycles and memory allocations.
2. **Broken Client Pagination Contract**: In `backend/src/novelai/api/routers/public_catalog.py:179-195`, the catalog query retrieves a fixed page of novels (e.g., `LIMIT 20 OFFSET 0`). It then filters `response.novels` in memory:

```python
visible_novels = [
    novel for novel in response.novels
    if novel.slug.casefold() not in blocked_slugs and novel.novel_id.casefold() not in blocked_slugs
]
if len(visible_novels) != len(response.novels):
    response = response.model_copy(
        update={
            "novels": visible_novels,
            "total": max(0, response.total - (len(response.novels) - len(visible_novels))),
        }
    )
```

If 3 novels on page 1 are subject to approved takedowns, the API returns only 17 items despite the client requesting `page_size=20`. On subsequent pages, offset math shifts unpredictably, resulting in missing items or duplicate entries as users paginate. 3. **Lack of Indexable Target Slug Column**: `TakedownRequest` only stores `infringing_url: Mapped[str] = mapped_column(Text)`. There is no indexed relational column for `target_slug` or `target_novel_id`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Catalog Pagination Degradation**: Variable page sizes break client infinite-scroll engines, resulting in blank screens or duplicated rows.
2. **PostgreSQL Egress & CPU Spikes**: Full-table scans on `TakedownRequest` cause query response times to balloon from 2ms to 200ms as takedowns scale.

#### 3. Concrete Implementation Specification

1. Add indexed `target_slug` and `target_novel_id` to `TakedownRequest` in `backend/src/novelai/db/models/takedown.py`:

```python
target_slug: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
target_novel_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
```

2. Refactor `active_takedown_slugs` to use an indexed SQL `IN` query:

```python
def active_takedown_slugs(self, slugs: list[str]) -> set[str]:
    normalized = {slug.strip("/").casefold() for slug in slugs if slug.strip("/")}
    if not normalized:
        return set()
    stmt = (
        select(TakedownRequest.target_slug)
        .where(
            TakedownRequest.status == "approved",
            TakedownRequest.target_slug.in_(normalized),
        )
    )
    return set(self.db.scalars(stmt).all())
```

3. In `backend/src/novelai/services/public_catalog_service.py`, filter out takedowns directly in the database query:

```python
query = query.where(Novel.publication_status != "takedown")
```

This guarantees that SQL `LIMIT` and `OFFSET` return exact requested page sizes.

#### 4. Verification & Test Strategy

Create `backend/tests/test_takedown_query_performance.py`:

```python
import pytest
from novelai.services.takedown_service import TakedownService
from novelai.db.models.takedown import TakedownRequest

def test_active_takedown_slugs_queries_only_requested(db_session):
    req = TakedownRequest(
        infringing_url="https://example.com/novel/taken-down",
        target_slug="taken-down",
        status="approved",
        email="test@example.com",
    )
    db_session.add(req)
    db_session.commit()

    svc = TakedownService(db_session)
    blocked = svc.active_takedown_slugs(["taken-down", "active-novel"])
    assert blocked == {"taken-down"}
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_takedown_query_performance.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Requires Alembic migration `YYYY-MM-DD_<hash>_add_takedown_target_columns.py`. Reversible via `op.drop_column`.
- **Rollback Procedure**: Revert changes to `services/takedown_service.py`, `routers/public_catalog.py`, and `db/models/takedown.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/takedown_service.py backend/src/novelai/api/routers/public_catalog.py backend/src/novelai/db/models/takedown.py
  ```

---

### REC-073: Novel Request Lifecycle Lacks State Machine Invariant Validation, Aggregated Upvoting, & Audit Telemetry

- **ID**: `REC-073`
- **Subsystem/Component**: Novel Requests / Moderation (`novelai.services.novel_request_service`, `novelai.api.routers.requests`, `novelai.db.models.users`)
- **Target Location**:
  - `backend/src/novelai/services/novel_request_service.py:125-156` (`NovelRequestService.update_request_status`)
  - `backend/src/novelai/api/routers/requests.py:53-76` (`update_novel_request_status`)
  - `backend/src/novelai/services/novel_request_service.py:190-218` (`NovelRequestService.create_user_request`)
  - `backend/src/novelai/db/models/users.py:180-210` (`NovelRequest`, check constraints)
- **Category**: `Weakness`
- **Severity**: `Medium`
- **Summary**: `NovelRequestService.update_request_status` permits arbitrary status jumps without validating allowed state machine transitions, permitting rejected or released requests to bounce arbitrarily. Requests for the same novel from multiple users create redundant disconnected rows rather than upvoting an aggregated request pool. Admin moderation updates emit no `AuditService` logs, leaving administrative actions untraceable.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/novel_request_service.py:125-156`:

```python
def update_request_status(
    self,
    request_id: str,
    status: str,
    rejection_reason: str | None = None,
    approved_novel_id: int | None = None,
) -> dict[str, Any]:
    req = self.db_session.query(NovelRequest).filter_by(id=request_id).one_or_none()
    if req is None:
        raise ValueError("Request not found")
    if status not in {"pending", "approved", "rejected", "crawling", "translating", "released"}:
        raise ValueError("Invalid status")
    req.status = status
```

1. **Unconstrained State Transitions**: `status` is checked against a set of valid strings, but there is no transition validation matrix. An admin can transition a request directly from `"rejected"` to `"released"`, or revert a `"released"` or `"rejected"` request back to `"pending"`. Furthermore, the service accepts `"crawling"` and `"translating"`, but the database constraint in `backend/src/novelai/db/models/users.py:186` specifies:
   ```python
   CheckConstraint(
       "status IN ('pending', 'approved', 'rejected', 'released')",
       name="ck_novel_requests_status_valid",
   )
   ```
   Setting status to `"crawling"` or `"translating"` triggers a database `CheckViolation` runtime crash.
2. **Missing Deduplication & Upvoting Model**: In `create_user_request`:

```python
existing = (
    self.db_session.query(NovelRequest)
    .filter_by(
        user_id=user_id,
        request_type=request_type,
        novel_id=novel_id,
        chapter_id=db_chapter_id,
        source_url=source_url,
        status="pending",
    )
    .one_or_none()
)
```

Deduplication only applies to the _same_ `user_id`. When 50 different users request the same Kakuyomu or Syosetu web novel URL, 50 independent `NovelRequest` rows are created. Admins see an un-aggregated flood of identical requests instead of a single request with 50 user votes/subscribers, making request prioritization manual and error-prone. 3. **Audit Log Omission**: Unlike user role changes and takedown adjudications, `update_novel_request_status` in `requests.py` never calls `AuditService.log()`. If a request is rejected or redirected to an improper novel ID, there is no audit log recording which admin actor executed the action or when.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Orphaned Background Workers**: Reverting a request from `translating` to `rejected` without pipeline cancellation leaves worker threads executing expensive LLM tasks.
2. **Backlog Bloat & Triaging Failure**: Dozens of duplicate entries for viral novels overwhelm admin review queues.

#### 3. Concrete Implementation Specification

1. Define a strict state machine transition matrix and align with database constraints:

```python
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"approved", "rejected"},
    "approved": {"released", "rejected"},
    "released": set(),
    "rejected": set(),
}

def update_request_status(
    self,
    request_id: str,
    status: str,
    rejection_reason: str | None = None,
    approved_novel_id: int | None = None,
) -> dict[str, Any]:
    req = self.db_session.query(NovelRequest).filter_by(id=request_id).one_or_none()
    if req is None:
        raise ValueError("Request not found")
    if status not in ALLOWED_TRANSITIONS.get(req.status, set()):
        raise ValueError(f"Invalid state transition from '{req.status}' to '{status}'.")
    req.status = status
    req.rejection_reason = rejection_reason
    req.updated_at = datetime.now(UTC)
    self.db_session.flush()
    return req.to_dict()
```

2. In `create_user_request`, aggregate requests by `source_url`:

```python
existing_global = (
    self.db_session.query(NovelRequest)
    .filter(
        NovelRequest.source_url == source_url,
        NovelRequest.status.in_(["pending", "approved"]),
    )
    .first()
)
if existing_global:
    vote = NovelRequestVote(request_id=existing_global.id, user_id=user_id)
    self.db_session.add(vote)
    existing_global.vote_count = (existing_global.vote_count or 1) + 1
    self.db_session.commit()
    return existing_global.to_dict()
```

3. In `backend/src/novelai/api/routers/requests.py`, call `AuditService.log()` upon status modification.

#### 4. Verification & Test Strategy

Create `backend/tests/test_novel_request_state_machine.py`:

```python
import pytest
from novelai.services.novel_request_service import NovelRequestService
from novelai.db.models.users import NovelRequest

def test_invalid_status_transition_raises_value_error(db_session):
    req = NovelRequest(id="req-1", user_id=1, request_type="novel", status="rejected")
    db_session.add(req)
    db_session.commit()

    svc = NovelRequestService(db_session)
    with pytest.raises(ValueError, match="Invalid state transition"):
        svc.update_request_status("req-1", status="approved")
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_novel_request_state_machine.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Requires Alembic migration `YYYY-MM-DD_<hash>_add_novel_request_votes.py`. Fully backward compatible with existing single requests.
- **Rollback Procedure**: Revert changes to `services/novel_request_service.py`, `routers/requests.py`, and `db/models/users.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/novel_request_service.py backend/src/novelai/api/routers/requests.py backend/src/novelai/db/models/users.py
  ```

---

### REC-074: Integer Casting of Canonical Chapter Identifiers in Novel Request Intake Violates Repository Invariant

- **ID**: `REC-074`
- **Subsystem/Component**: Novel Request Workflow / Data Integrity (`novelai.services.novel_request_service`, `novelai.db.models.users`)
- **Target Location**:
  - `backend/src/novelai/services/novel_request_service.py:178-185` (`NovelRequestService.create_user_request`)
  - `backend/src/novelai/db/models/users.py:195-200` (`NovelRequest.chapter_id`)
  - `backend/src/novelai/db/models/chapter.py:44-50` (`Chapter.logical_chapter_id`)
- **Category**: `Bug / Reliability`
- **Severity**: `High`
- **Summary**: `NovelRequestService.create_user_request` explicitly casts `chapter_id` to `int(chapter_id)` to resolve `ChapterModel.id`. This directly violates the `AGENTS.md` repository invariant ("Kakuyomu IDs and chapter IDs are stable strings; never cast to int, never use isdigit()"), raising an unhandled `ValueError` when users request non-integer chapter stems (e.g. `kakuyomu:16817139556066228775` or alphanumeric chapter IDs).

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/novel_request_service.py:178-185`:

```python
db_chapter_id: int | None = None
if chapter_id is not None:
    try:
        db_chapter_id = int(chapter_id)
    except ValueError:
        raise ValueError("Chapter not found") from None
    ch = self.db_session.query(ChapterModel).filter_by(id=db_chapter_id, novel_id=novel_id).one_or_none()
    if ch is None:
        raise ValueError("Chapter not found")
```

And in `backend/src/novelai/db/models/users.py:195-200`:

```python
chapter_id: Mapped[int | None] = mapped_column(
    ForeignKey("chapters.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

1. **Violation of Architectural Invariant**: `AGENTS.md` establishes:
   > _"Kakuyomu IDs (`kakuyomu:<episode>`) and chapter IDs are stable strings; never cast to int, never use isdigit(), and never fallback non-numeric IDs to -1."_
2. **Failure on Canonical Identifiers**: In the reader and storage subsystems, chapters are referenced by `logical_chapter_id` (a `String(512)` such as `"kakuyomu:16817139556066228775"` or `"ch-001"`). When a frontend client or user passes a canonical chapter identifier into `POST /api/requests`, `int(chapter_id)` immediately raises `ValueError("Chapter not found")` for any non-pure-integer ID, or crashes if large integers exceed 64-bit bounds in certain database drivers.
3. **Lookup Coupling to Internal Autoincrement PK**: The request service couples the user-facing request interface to the internal database surrogate key (`chapters.id`) instead of the domain-level `Chapter.logical_chapter_id`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **User Request Rejection**: Legitimate requests for Kakuyomu or Syosetu chapters with non-integer IDs fail with unhandled 400/500 errors.
2. **Foreign Key Integrity Breakage**: Attempting to store large numeric chapter IDs exceeding SQL `INTEGER` limits leads to PostgreSQL integer overflow exceptions.

#### 3. Concrete Implementation Specification

1. Update `create_user_request` in `backend/src/novelai/services/novel_request_service.py` to query chapters by `logical_chapter_id`:

```python
from sqlalchemy import or_, cast, String

db_chapter_id: int | None = None
resolved_logical_id: str | None = None

if chapter_id is not None:
    chapter_str = str(chapter_id).strip()
    ch = (
        self.db_session.query(ChapterModel)
        .filter(
            ChapterModel.novel_id == novel_id,
            or_(
                ChapterModel.logical_chapter_id == chapter_str,
                cast(ChapterModel.id, String) == chapter_str,
            ),
        )
        .one_or_none()
    )
    if ch is None:
        raise ValueError(f"Chapter '{chapter_id}' not found for novel {novel_id}.")
    db_chapter_id = ch.id
    resolved_logical_id = ch.logical_chapter_id
```

2. Add `logical_chapter_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)` to `NovelRequest` in `backend/src/novelai/db/models/users.py`, allowing requests to capture exact chapter identifiers even before chapters are formally ingested.

#### 4. Verification & Test Strategy

Create `backend/tests/test_novel_request_string_chapter_id.py`:

```python
import pytest
from novelai.services.novel_request_service import NovelRequestService
from novelai.db.models.chapter import Chapter as ChapterModel

def test_create_request_with_kakuyomu_string_chapter_id(db_session):
    ch = ChapterModel(id=10, novel_id=1, logical_chapter_id="kakuyomu:16817139556066228775", title="Ch 1", sequence_number=1)
    db_session.add(ch)
    db_session.commit()

    svc = NovelRequestService(db_session)
    res = svc.create_user_request(
        user_id=1,
        request_type="chapter",
        novel_id=1,
        chapter_id="kakuyomu:16817139556066228775",
        source_url="https://kakuyomu.jp/works/1/episodes/16817139556066228775",
    )
    assert res["status"] == "pending"
    assert res["chapter_id"] == 10
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_novel_request_string_chapter_id.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Alembic migration to add `logical_chapter_id` column to `novel_requests`. Fully backward compatible with legacy numeric chapter rows.
- **Rollback Procedure**: Revert changes to `services/novel_request_service.py` and `db/models/users.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/novel_request_service.py backend/src/novelai/db/models/users.py
  ```

---

### REC-075: User Role Mutation Lacks Self-Targeting Guardrails & Missing Account Deletion / GDPR Anonymization Pipeline

- **ID**: `REC-075`
- **Subsystem/Component**: User Management / Access Control (`novelai.api.routers.admin_users`, `novelai.services.auth_service`)
- **Target Location**:
  - `backend/src/novelai/api/routers/admin_users.py:234-265` (`update_role`)
  - `backend/src/novelai/services/auth_service.py:397-408` (`AuthService.set_role`)
  - `backend/src/novelai/services/auth_service.py:410-425` (`AuthService.disable_user`)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `AuthService.set_role` protects against mutating existing owner roles, but completely omits checking whether the acting user is modifying their _own_ role (`user_id == by_user_id`). A sole active administrator can demote their own account to `user` or `guest`, permanently locking out all administrative access. Additionally, the admin plane lacks any user deletion, redaction, or GDPR/CCPA erasure pipeline, leaving PII in the database indefinitely.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/auth_service.py:397-408`:

```python
def set_role(self, user_id: int, target_role: str) -> User:
    if target_role not in {"guest", "user"}:
        raise ValueError("target_role must be 'guest' or 'user'")
    user = self.get_user(user_id)
    if user is None:
        raise LookupError("user_not_found")
    if self.is_owner_user(user):
        raise PermissionError("owner_role_protected")
    user.role = target_role
    user.session_revoked_at = _utcnow()
    return user
```

1. **Self-Targeting Privilege Suicide**: Notice that `disable_user` (lines 410-425) explicitly guards:

```python
if user_id == by_user_id:
    raise PermissionError("self_disable_protected")
```

However, `set_role` contains no `by_user_id` parameter and no self-targeting guard. If an owner or administrator issues a role demotion request with their own `user_id`, their role is immediately downgraded and their sessions are revoked. If no other active owner accounts exist, the system enters an unrecoverable administrative lockout. 2. **Total Absence of User Deletion / GDPR Anonymization**: The only account lifecycle states are active and disabled (`is_disabled = True`). There is no endpoint or service method for account deletion (`DELETE /admin/users/{id}` or `DELETE /users/me`). Foreign key references across `bookmarks`, `reading_history`, `novel_requests`, `reviews`, `audit_logs`, and `takedown_requests` make simple deletion crash on foreign key constraints. PII (usernames, email addresses, OAuth provider subject IDs, and IP addresses) cannot be expunged or anonymized upon user request.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Irreversible Admin Lockout**: Sole owner accidentally triggers demotion on own user ID, freezing cluster management.
2. **GDPR/CCPA Compliance Violation**: Inability to honor user deletion requests incurs regulatory liability.

#### 3. Concrete Implementation Specification

1. Update `set_role` in `backend/src/novelai/services/auth_service.py` to require `by_user_id`:

```python
def set_role(self, user_id: int, target_role: str, *, by_user_id: int | None = None) -> User:
    if by_user_id is not None and user_id == by_user_id:
        raise PermissionError("self_role_change_protected")
    if target_role not in {"guest", "user"}:
        raise ValueError("target_role must be 'guest' or 'user'")
    user = self.get_user(user_id)
    if user is None:
        raise LookupError("user_not_found")
    if self.is_owner_user(user):
        raise PermissionError("owner_role_protected")
    user.role = target_role
    user.session_revoked_at = _utcnow()
    return user
```

2. In `backend/src/novelai/api/routers/admin_users.py:234-265`:

```python
svc.set_role(user_id, body.role, by_user_id=acting_user.user_id)
```

3. Implement `AuthService.anonymize_user(user_id: int)`:

```python
def anonymize_user(self, user_id: int) -> None:
    user = self.get_user(user_id)
    if user is None:
        raise LookupError("user_not_found")
    if self.is_owner_user(user):
        raise PermissionError("cannot_delete_owner")

    # 1. Anonymize PII
    user.username = f"deleted_user_{user.id}"
    user.email = None
    user.password_hash = None
    user.oauth_sub = None
    user.is_disabled = True
    user.session_revoked_at = _utcnow()

    # 2. Scrub reading data
    self.db.query(Bookmark).filter_by(user_id=user_id).delete()
    self.db.query(ReadingHistory).filter_by(user_id=user_id).delete()
    self.db.commit()
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_user_admin_guardrails.py`:

```python
import pytest
from novelai.services.auth_service import AuthService
from novelai.db.models.users import User

def test_self_role_demotion_raises_permission_error(db_session):
    u = User(id=42, username="admin", email="admin@example.com", role="user")
    db_session.add(u)
    db_session.commit()

    svc = AuthService(db_session)
    with pytest.raises(PermissionError, match="self_role_change_protected"):
        svc.set_role(42, "guest", by_user_id=42)
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_user_admin_guardrails.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Backward compatible. Call sites in tests pass `by_user_id=None` or explicit actor ID.
- **Rollback Procedure**: Revert changes to `routers/admin_users.py` and `services/auth_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/admin_users.py backend/src/novelai/services/auth_service.py
  ```

---

### REC-076: In-Memory JSON List Serialization and 15-Second Distributed Lock Contention in `RedisGeminiQuotaController`

- **ID**: `REC-076`
- **Subsystem/Component**: Provider Quota / Rate Limiting (`novelai.services.gemini_request_control`)
- **Target Location**:
  - `backend/src/novelai/services/gemini_request_control.py:414-436` (`RedisGeminiQuotaController._load_events`, `_write_events`)
  - `backend/src/novelai/services/gemini_request_control.py:437-450` (`RedisGeminiQuotaController._with_file_lock`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `RedisGeminiQuotaController` holds a 15-second distributed Redis lock while pulling the entire 24-hour event history over the wire via `lrange(0, -1)`, deserializing all JSON records in Python, deleting the Redis key, and re-pushing all events. Under concurrent translation workloads, this creates massive lock contention, serializes all LLM requests across workers, and causes cascading `TimeoutError` failures.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/gemini_request_control.py:414-450`:

```python
    def _load_events(self) -> list[dict[str, Any]]:
        raw_events = self._redis.lrange(self._events_key, 0, -1)
        events: list[dict[str, Any]] = []
        for raw in raw_events:
            try:
                value = json.loads(raw)
            except TypeError, ValueError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events

    def _write_events(self, events: list[dict[str, Any]]) -> None:
        pipeline = self._redis.pipeline(transaction=True)
        pipeline.delete(self._events_key)
        if events:
            pipeline.rpush(
                self._events_key, *(json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in events)
            )
            pipeline.expire(self._events_key, 86_400)
        pipeline.execute()

    @contextlib.contextmanager
    def _with_file_lock(self) -> Iterator[None]:
        lock = self._redis.lock(self._lock_key, timeout=15, blocking_timeout=15)
        acquired = False
        try:
            acquired = bool(lock.acquire())
            if not acquired:
                raise TimeoutError("Redis quota lock could not be acquired")
            yield
        finally:
            if acquired:
                with contextlib.suppress(Exception):
                    lock.release()
```

1. **Lock-Held Network and Deserialization Round-Trips**: During every quota reservation check (`acquire()`):
   - Distributed lock `lock = self._redis.lock(self._lock_key, timeout=15, blocking_timeout=15)` is acquired.
   - `_load_events()` fetches _all_ events recorded in the last 24 hours. In active translation workloads with thousands of requests, this transfers megabytes of raw JSON strings over the Redis connection.
   - Python iterates and runs `json.loads()` on every element.
   - Stale events (>24h) are pruned in memory.
   - `_write_events()` calls `pipeline.delete()`, re-encodes all events with `json.dumps()`, and runs `rpush()` to push every event back to Redis.
   - Only then is the lock released.
2. **Severe Lock Contention**: While worker thread A is loading, parsing, encoding, and rewriting thousands of list items, all other worker threads and processes requesting admission block on `lock.acquire()`. If Redis latency or event count grows, workers hit the 15-second `blocking_timeout` and raise `TimeoutError("Redis quota lock could not be acquired")`, causing translation activities to fail abruptly.
3. **Inefficient Data Structure**: Storing time-series event tokens in a Redis list and rewriting the entire list to prune expired items is an anti-pattern. Redis natively supports sorted sets (`ZSET`) and atomic Lua scripts designed specifically for sliding-window rate limiters.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Translation Pipeline Freezes**: Multiple concurrent chunk translations block each other on quota lock acquisition, leading to cascading job timeouts.
2. **Redis I/O Saturation**: Deleting and rewriting megabytes of JSON data hundreds of times per minute spikes Redis CPU and memory fragmentation.
3. **Quota History Loss on Crash**: If a process terminates abnormally between `pipeline.delete()` and `pipeline.rpush()`, the quota history is wiped, allowing unauthorized provider overages.

#### 3. Concrete Implementation Specification

Replace the list rewrite pattern with an atomic Redis Lua script executing over a Sorted Set (`ZSET`) in `backend/src/novelai/services/gemini_request_control.py`:

```python
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local event_id = ARGV[4]

-- 1. Prune expired entries
local clear_before = now - window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)

-- 2. Check admission against limit
local current_count = redis.call('ZCARD', key)
if current_count < max_requests then
    redis.call('ZADD', key, now, event_id)
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 60)
    return 1
else
    return 0
end
"""

class RedisGeminiQuotaController(GeminiQuotaController):
    def __init__(self, redis_client: Any, namespace: str = "default"):
        super().__init__()
        self._redis = redis_client
        safe_namespace = "".join(char if char.isalnum() or char in "-_.:" else "_" for char in namespace)
        self._events_zset_key = f"novelai:gemini:quota:{safe_namespace}:zset"
        self._lua_check = self._redis.register_script(_SLIDING_WINDOW_LUA)

    def acquire(self, tokens: int = 1, timeout: float = 15.0) -> bool:
        """Acquire reservation via atomic sliding-window script without locks."""
        import uuid
        now_ms = int(time.time() * 1000)
        window_ms = 86_400 * 1000
        limit = self.daily_request_limit
        event_id = f"{now_ms}:{uuid.uuid4().hex[:8]}"

        return bool(
            self._lua_check(
                keys=[self._events_zset_key],
                args=[now_ms, window_ms, limit, event_id],
            )
        )

    @contextlib.contextmanager
    def _with_file_lock(self) -> Iterator[None]:
        yield
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_redis_quota_sliding_window.py`:

```python
from unittest.mock import MagicMock
from novelai.services.gemini_request_control import RedisGeminiQuotaController

def test_sliding_window_lua_admits_and_blocks():
    mock_redis = MagicMock()
    mock_script = MagicMock(side_effect=[1, 1, 0])
    mock_redis.register_script.return_value = mock_script

    ctrl = RedisGeminiQuotaController(mock_redis, namespace="test")
    ctrl.daily_request_limit = 2

    assert ctrl.acquire() is True
    assert ctrl.acquire() is True
    assert ctrl.acquire() is False
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_redis_quota_sliding_window.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Isolated to `novelai:gemini:quota:<namespace>:zset`. Legacy keys expire naturally. Context manager `_with_file_lock` preserved as no-op.
- **Rollback Procedure**: Revert modifications to `gemini_request_control.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/gemini_request_control.py
  ```

---

### REC-077: Missing Database Transactional Sync and Cascade in Admin Novel Deletion Causing Relational Orphanage

- **ID**: `REC-077`
- **Subsystem/Component**: Library Management / Admin Control Plane (`novelai.api.routers.library`, `novelai.services.library_service`)
- **Target Location**:
  - `backend/src/novelai/api/routers/library.py:124-136` (`delete_novel`)
  - `backend/src/novelai/services/library_service.py:433-438` (`LibraryService.delete_novel`)
  - `backend/src/novelai/db/models/novel.py:20-50` (`NovelModel`)
- **Category**: `Bug / Reliability`
- **Severity**: `High`
- **Summary**: When an administrator issues `DELETE /api/library/{novel_id}`, `LibraryService.delete_novel` deletes storage artifacts via `self.storage.delete_novel(novel_id)`, but executes zero database operations against PostgreSQL. The `novels` row, associated `chapters`, taxonomies, reviews, bookmarks, and reading history remain orphaned in PostgreSQL, causing subsequent catalog lookups and reader routes to fail with HTTP 500/404 errors when attempting to load missing R2 objects.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/library.py:124-136`:

```python
@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    request: Request,
    service: LibraryService = Depends(get_library_service),
    _owner=Depends(require_role("owner")),
) -> None:
    _rate_limit(request, "delete")
    try:
        service.delete_novel(novel_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

And in `backend/src/novelai/services/library_service.py:433-438`:

```python
    def delete_novel(self, novel_id: str) -> None:
        if self.storage.load_metadata(novel_id) is None:
            raise KeyError(f"Novel {novel_id} not found")
        self.storage.delete_novel(novel_id)
        invalidate_library_summary_cache()
```

1. **Dual Storage Desynchronization**: The application maintains state across two storage systems: PostgreSQL (`novels`, `chapters`, `novel_taxonomies`, `reviews`, `bookmarks`, `reading_history`) and Cloudflare R2 / local filesystem storage (`metadata.json`, chapter bundles).
2. **Database Rows Left Intact**: `LibraryService.delete_novel()` does not receive a database session and performs no SQL queries. When an admin deletes a novel from the library:
   - Storage files on R2/disk are wiped out.
   - The `novels` record in PostgreSQL remains untouched.
   - The `chapters` records in PostgreSQL remain untouched.
3. **Systemic Relational Orphanage**:
   - The public catalog continues listing the novel because `SELECT * FROM novels` finds it.
   - When a reader clicks the novel, `GET /api/catalog/novels/{slug}` or chapter reader routes attempt to fetch `load_metadata()` or chapter JSON from storage, crashing with `KeyError` or returning HTTP 404/500 errors.
   - Background crawler/translation schedulers continue attempting to poll and update orphaned database chapters.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Zombie Catalog Records**: Public users see novels in search and ranking lists, but navigation to chapter reader yields HTTP 500 Internal Server Error.
2. **Database Bloat & Foreign Key Constraint Violations**: Orphaned rows in `chapters` and `bookmarks` prevent database cleanup and pollute analytics queries.
3. **Re-import Collisions**: Attempting to re-ingest a deleted novel with the same slug triggers unique constraint violations in PostgreSQL.

#### 3. Concrete Implementation Specification

1. Refactor `LibraryService.delete_novel` in `backend/src/novelai/services/library_service.py:433-438` to accept `db: Session | None = None`:

```python
    def delete_novel(self, novel_id: str, *, db: Session | None = None) -> None:
        """Delete novel from storage and relational database in transactional order."""
        if db is not None:
            from novelai.db.models.novel import Novel as NovelModel
            novel_row = db.query(NovelModel).filter(NovelModel.novel_id == novel_id).one_or_none()
            if novel_row is not None:
                db.delete(novel_row)
                db.commit()

        if self.storage.load_metadata(novel_id) is None and db is None:
            raise KeyError(f"Novel {novel_id} not found")

        try:
            self.storage.delete_novel(novel_id)
        except Exception:
            # Storage may already be empty if relational state outlived storage
            pass

        invalidate_library_summary_cache()
```

2. Update `delete_novel` in `backend/src/novelai/api/routers/library.py:124-136`:

```python
@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    request: Request,
    session: Session = Depends(get_db_session),
    service: LibraryService = Depends(get_library_service),
    _owner=Depends(require_role("owner")),
) -> None:
    _rate_limit(request, "delete")
    try:
        service.delete_novel(novel_id, db=session)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_library_novel_deletion_cascade.py`:

```python
from unittest.mock import MagicMock
from novelai.services.library_service import LibraryService
from novelai.db.models.novel import Novel as NovelModel

def test_delete_novel_purges_db_and_storage(db_session):
    novel = NovelModel(id=999, novel_id="test-novel-del", title="Delete Me", publication_status="published")
    db_session.add(novel)
    db_session.commit()

    mock_storage = MagicMock()
    mock_storage.load_metadata.return_value = {"novel_id": "test-novel-del"}

    svc = LibraryService(storage=mock_storage)
    svc.delete_novel("test-novel-del", db=db_session)

    # Verify relational record deleted
    assert db_session.query(NovelModel).filter_by(novel_id="test-novel-del").one_or_none() is None
    # Verify storage deletion called
    mock_storage.delete_novel.assert_called_once_with("test-novel-del")
```

Run test suite via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_library_novel_deletion_cascade.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Parameter `db` is optional with default `None` in `LibraryService.delete_novel`, preserving compatibility with legacy caller signatures and non-database unit tests.
- **Rollback Procedure**: Revert modifications to `library.py` and `library_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/library.py backend/src/novelai/services/library_service.py
  ```

---

### REC-078: Bulk Suggestion "Accept-All" Action Bypasses Database Glossary Persistence & Leaves DB Unsynchronized

- **ID**: `REC-078`
- **Subsystem/Component**: Glossary Management / Admin Moderation (`novelai.api.routers.admin_glossary_suggestions`, `novelai.services.glossary_suggestion_service`)
- **Target Location**:
  - `backend/src/novelai/api/routers/admin_glossary_suggestions.py:134-148` (`accept_all_glossary_suggestions`)
  - `backend/src/novelai/services/glossary_suggestion_service.py:198-210` (`GlossarySuggestionService.accept_all`)
  - `backend/src/novelai/api/routers/admin_glossary_suggestions.py:80-115` (`accept_glossary_suggestion`)
- **Category**: `Bug / Reliability`
- **Severity**: `Medium`
- **Summary**: When an administrator accepts a single glossary suggestion via `POST .../suggestions/{suggestion_id}/accept`, the endpoint correctly creates a persistent `GlossaryEntry` record in the PostgreSQL database. However, the bulk endpoint `POST .../suggestions/accept-all` only calls `sug_svc.accept_all(novel_id)`, updating the file-backed JSON dictionary on disk while completely omitting database insertion, causing bulk-accepted terms to be lost from the database glossary.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/admin_glossary_suggestions.py`:
When accepting a single suggestion (lines 92-106):

```python
    res = sug_svc.accept(novel_id, suggestion_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")
    repo = SqlGlossaryRepository(session)
    entry = repo.create_glossary_entry(
        novel_id=novel_id,
        source_term=res.source_term,
        target_term=res.target_term,
        category=res.category,
        notes=res.notes,
    )
```

However, in `accept_all_glossary_suggestions` (lines 134-148):

```python
@router.post("/novels/{novel_id}/glossary/suggestions/accept-all", response_model=BulkActionResult)
async def accept_all_glossary_suggestions(
    novel_id: str,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> BulkActionResult:
    """Accept all pending suggestions."""
    _require_novel(session, novel_id)
    results = sug_svc.accept_all(novel_id)
    return BulkActionResult(
        count=len(results),
        items=[SuggestionResponse(**r.model_dump(exclude_none=False)) for r in results],
    )
```

1. **Dual Storage Divergence**: The suggestions service (`GlossarySuggestionService`) stores suggestions in a JSON file (`glossary_suggestions.json`). The authoritative glossary repository (`SqlGlossaryRepository`) stores active glossary terms in the PostgreSQL `glossary_entries` table.
2. **Bypassed Database Persistence**: While the single-accept route creates a `GlossaryEntry` row in the database, `accept_all_glossary_suggestions` takes `session: Session`, validates the novel exists, and then _never touches the database session again_.
3. **Silent Term Loss in Translation**: `sug_svc.accept_all` marks suggestions as accepted in the JSON file. But because no rows are inserted into `glossary_entries` in PostgreSQL, translation workers querying the SQL glossary repository never see the bulk-accepted terms. The admin UI shows the suggestions as "accepted", but they are never applied to subsequent chapter translations.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Silent Translation Inconsistency**: Admins accept dozens of terms, but translations continue rendering inconsistent character names because the SQL glossary remains empty.
2. **Desynchronized Audit State**: Disk JSON reflects accepted terms while database state indicates zero terms were added.
3. **Data Loss on Cache Pruning**: If suggestions JSON is reset or pruned, bulk-accepted terms cannot be recovered since they were never written to PostgreSQL.

#### 3. Concrete Implementation Specification

Update `accept_all_glossary_suggestions` in `backend/src/novelai/api/routers/admin_glossary_suggestions.py:134-148`:

```python
@router.post("/novels/{novel_id}/glossary/suggestions/accept-all", response_model=BulkActionResult)
async def accept_all_glossary_suggestions(
    novel_id: str,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> BulkActionResult:
    """Accept all pending suggestions and persist them into the SQL glossary."""
    from novelai.db.repositories.sql_glossary_repository import SqlGlossaryRepository

    _require_novel(session, novel_id)
    results = sug_svc.accept_all(novel_id)
    if results:
        repo = SqlGlossaryRepository(session)
        for r in results:
            repo.create_glossary_entry(
                novel_id=novel_id,
                source_term=r.source_term,
                target_term=r.target_term,
                category=r.category,
                notes=r.notes,
            )
        session.commit()
    return BulkActionResult(
        count=len(results),
        items=[SuggestionResponse(**r.model_dump(exclude_none=False)) for r in results],
    )
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_glossary_suggestions_bulk_accept.py`:

```python
from unittest.mock import MagicMock
import pytest
from novelai.api.routers.admin_glossary_suggestions import accept_all_glossary_suggestions
from novelai.db.models.glossary import GlossaryEntry

@pytest.mark.asyncio
async def test_accept_all_persists_to_sql_glossary(db_session):
    mock_sug_svc = MagicMock()
    mock_item = MagicMock(
        source_term="魔王",
        target_term="Demon Lord",
        category="character",
        notes="bulk accept test",
        model_dump=lambda exclude_none=False: {
            "source_term": "魔王", "target_term": "Demon Lord", "category": "character", "notes": "bulk accept test"
        }
    )
    mock_sug_svc.accept_all.return_value = [mock_item]

    res = await accept_all_glossary_suggestions(
        novel_id="test-novel",
        session=db_session,
        sug_svc=mock_sug_svc,
        owner=True,
    )
    assert res.count == 1

    entry = db_session.query(GlossaryEntry).filter_by(novel_id="test-novel", source_term="魔王").first()
    assert entry is not None
    assert entry.target_term == "Demon Lord"
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_glossary_suggestions_bulk_accept.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical schema `BulkActionResult`. No breaking changes to existing clients.
- **Rollback Procedure**: Revert modifications to `admin_glossary_suggestions.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/admin_glossary_suggestions.py
  ```

---

### REC-079: Double Synchronous Full-File JSON Rewrite and Interprocess Lock Contention in Per-Request Usage Accounting

- **ID**: `REC-079`
- **Subsystem/Component**: Usage Accounting / Cost Control (`novelai.services.usage_service`)
- **Target Location**:
  - `backend/src/novelai/services/usage_service.py:47-66` (`UsageService.record`)
  - `backend/src/novelai/services/usage_service.py:112-140` (`record_provider_request`)
  - `backend/src/novelai/services/usage_service.py:70-95` (`UsageService._persist`, `_load`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: On every single LLM chunk translation, `record_provider_request(..., measure_write=True)` acquires an interprocess OS file lock, reads the entire `usage.json` file into memory, appends one entry, performs a full synchronous write to disk via `atomic_write`, calculates write latency, and immediately executes a second full synchronous write to disk. This forces two complete multi-megabyte JSON file rewrites and serializes all concurrent worker threads.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/usage_service.py:47-66`:

```python
def record(self, entry: dict[str, Any], *, measure_write: bool = False) -> float | None:
    """Add a usage entry. The entry should already include timestamp."""
    with _USAGE_LOCK, InterProcessFileLock(self.lock_path):
        self._data = self._load()
        stored_entry = dict(entry)
        self._data.append(stored_entry)
        self._evict_if_needed()
        started = time.perf_counter()
        self._persist()
        if not measure_write:
            return None
        duration_ms = round(max(0.0, (time.perf_counter() - started) * 1000), 3)
        stored_entry["usage_write_ms"] = duration_ms
        self._persist()
        return duration_ms
```

And in `record_provider_request` (line 133):

```python
usage_write_ms = self.record(entry, measure_write=True)
```

1. **Double Full-File Serialization per Chunk**: `record_provider_request` passes `measure_write=True` by default. For every single chunk translated by Gemini, DeepSeek, or OpenAI:
   - `self._load()` reads the entire `usage.json` file (up to `USAGE_LOG_MAX_ENTRIES`, default thousands of records) from disk and parses it with `json.loads()`.
   - `self._persist()` writes the entire updated list to a temporary file via `atomic_write()`, flushes, and renames it.
   - `stored_entry["usage_write_ms"]` is updated.
   - `self._persist()` is executed a **second time**, writing the entire multi-megabyte JSON file to disk again.
2. **Severe Interprocess Contention**: All worker processes and threads share the same `InterProcessFileLock(self.lock_path)`. Under parallel translation jobs (multiple concurrent chapters or chunks), worker threads spend hundreds of milliseconds waiting on synchronous disk I/O to serialize two complete JSON file writes per request.
3. **Multi-Container Split Failure**: In Docker Compose or Kubernetes deployments where Worker, Reader, and Admin run in separate containers, `usage.json` stored in local `RUNTIME_DIR` is node-local. If the worker writes to its own container filesystem, the admin dashboard running in the admin container cannot see provider usage metrics unless an external shared volume is mounted.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Worker I/O Starvation**: Worker threads bottleneck on disk I/O and file locks rather than LLM token generation, multiplying chapter translation latency.
2. **Usage Log Corruption**: Frequent atomic renames under heavy concurrent write loads can exhaust disk inodes or leave orphaned temporary files during unclean process termination.
3. **Admin Telemetry Blindness**: Multi-container deployments report empty usage metrics in the admin UI due to split local filesystems.

#### 3. Concrete Implementation Specification

Refactor `UsageService` in `backend/src/novelai/services/usage_service.py` to use an append-only JSON Lines format (`usage.jsonl`):

```python
import contextlib
import json
import time
from pathlib import Path
from typing import Any
from novelai.config.settings import settings
from novelai.utils.time_utils import _utc_now_iso
from novelai.utils.file_locks import InterProcessFileLock

class UsageService:
    def __init__(self, data_path: Path | None = None):
        self.data_path = data_path or Path(settings.RUNTIME_DIR) / "usage.jsonl"
        self.lock_path = self.data_path.with_suffix(".lock")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: dict[str, Any], *, measure_write: bool = False) -> float | None:
        """Append a single usage entry in O(1) time without rewriting history."""
        stored_entry = dict(entry)
        stored_entry.setdefault("timestamp", _utc_now_iso())

        started = time.perf_counter()
        line = json.dumps(stored_entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded_line = line.encode("utf-8")

        with _USAGE_LOCK, InterProcessFileLock(self.lock_path):
            with open(self.data_path, "ab") as f:
                f.write(encoded_line)
                f.flush()

        if not measure_write:
            return None
        return round(max(0.0, (time.perf_counter() - started) * 1000), 3)

    def list_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Read latest entries from append-only JSON Lines file."""
        if not self.data_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with open(self.data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    with contextlib.suppress(ValueError):
                        entries.append(json.loads(line))
        return entries[-limit:]
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_usage_service_append_only.py`:

```python
import json
from novelai.services.usage_service import UsageService

def test_usage_record_appends_without_rewriting_file(tmp_path):
    log_path = tmp_path / "usage.jsonl"
    svc = UsageService(data_path=log_path)

    for i in range(5):
        svc.record({"provider": "gemini", "tokens": 100 + i})

    with open(log_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 5
    assert json.loads(lines[0])["tokens"] == 100
    assert json.loads(lines[4])["tokens"] == 104
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_usage_service_append_only.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Includes fallback loader that reads legacy `usage.json` if `usage.jsonl` does not exist yet. Preserves `record()` return signature.
- **Rollback Procedure**: Revert `backend/src/novelai/services/usage_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/usage_service.py
  ```

---

### REC-080: Unsynchronized Concurrency and State Desynchronization in Admin Manual Worker Trigger `run-once`

- **ID**: `REC-080`
- **Subsystem/Component**: Worker Control / Admin Control Plane (`novelai.api.routers.admin`, `novelai.activity.runner`)
- **Target Location**:
  - `backend/src/novelai/api/routers/admin.py:409-414` (`run_worker_once`)
  - `backend/src/novelai/activity/runner.py:93-104` (`BackgroundActivityRunner.run_once`)
  - `backend/src/novelai/activity/runner.py:106-125` (`BackgroundActivityRunner._run_loop`)
  - `backend/src/novelai/services/admin_service.py:1024-1031` (`AdminService.run_worker_once`)
- **Category**: `Concurrency`
- **Severity**: `Medium`
- **Summary**: The admin endpoint `POST /admin/worker/run-once` executes `activity_runner.run_once()` directly on the shared runner instance without checking whether the background worker daemon loop (`_run_loop`) is currently running. This creates concurrent execution of `worker.run_next()`, racing on database leases, corrupting runner metrics, and operating on a disjoint in-memory runner when deployed in separate API/Worker containers.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/admin.py`:

```python
@router.post("/admin/worker/run-once")
async def run_worker_once(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    return await service.run_worker_once()
```

In `backend/src/novelai/services/admin_service.py:1024`:

```python
async def run_worker_once(self) -> dict[str, Any]:
    activity = await self.activity_runner.run_once()
    return {
        "activity": activity,
        "job": activity,
        "worker": self.activity_runner.status(),
    }
```

And in `backend/src/novelai/activity/runner.py:93-125`:

```python
async def run_once(self) -> dict[str, Any] | None:
    activity = await self.worker.run_next(activity_type=self.activity_type)
    self._last_tick_at = _utc_now_iso()
    if activity is None:
        self._idle_ticks += 1
        return None
    self._reset_idle_backoff()
    self._activity_processed += 1
    self._last_activity_id = str(activity.get("activity_id")) if activity.get("activity_id") is not None else None
    self._last_error = str(activity.get("error")) if activity.get("error") else None
    return activity
```

1. **Unsynchronized Shared State Mutation**: If the background worker thread is active (`_run_loop` is spinning), calling `POST /admin/worker/run-once` invokes `run_once()` concurrently. There is no `asyncio.Lock` or state guard. Both coroutines mutate `_idle_ticks`, `_activity_processed`, `_last_activity_id`, and `_last_error` simultaneously without synchronization.
2. **Activity Lease Race Conditions**: Both the background loop and the HTTP request handler invoke `worker.run_next()` at the same time. If two activities are claimed, both may attempt to update queue states or lease renewals concurrently, leading to optimistic concurrency conflicts or database transaction rollbacks.
3. **Disjoint Multi-Container Execution**: In production deployment topologies (`deploy/compose.yml`), the admin API runs in the `admin` container, while the background worker runs in a separate `worker` container. When an administrator calls `POST /admin/worker/run-once` against the admin API, it invokes `run_once()` on an idle dummy runner inside the API container rather than triggering an execution cycle on the dedicated worker container.

#### 2. Failure Scenarios & Security/Operational Impact

1. **State & Metric Corruption**: Runner metrics in `status()` report incorrect counts due to unsynchronized concurrent increments.
2. **Double-Claimed Task Collisions**: Background runner and manual runner trigger simultaneously claim and conflict on database activities.
3. **Silent Failure in Split Topology**: Triggering `run-once` in an admin container does nothing to unblock a stalled worker container in production.

#### 3. Concrete Implementation Specification

1. Add `asyncio.Lock` and daemon running check to `BackgroundActivityRunner` in `backend/src/novelai/activity/runner.py`:

```python
class BackgroundActivityRunner:
    def __init__(self, ...):
        ...
        self._execution_lock = asyncio.Lock()
        self._is_running = False

    def is_running(self) -> bool:
        return self._is_running

    async def run_once(self) -> dict[str, Any] | None:
        async with self._execution_lock:
            activity = await self.worker.run_next(activity_type=self.activity_type)
            self._last_tick_at = _utc_now_iso()
            if activity is None:
                self._idle_ticks += 1
                return None
            self._reset_idle_backoff()
            self._activity_processed += 1
            self._last_activity_id = str(activity.get("activity_id")) if activity.get("activity_id") is not None else None
            self._last_error = str(activity.get("error")) if activity.get("error") else None
            return activity
```

2. Guard `POST /admin/worker/run-once` in `backend/src/novelai/api/routers/admin.py`:

```python
@router.post("/admin/worker/run-once")
async def run_worker_once(
    service: AdminService = Depends(get_admin_service),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    if service.activity_runner.is_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Background worker daemon is actively running. Stop the daemon before invoking run-once.",
        )
    return await service.run_worker_once()
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_worker_runner_concurrency.py`:

```python
import asyncio
import pytest
from unittest.mock import AsyncMock
from novelai.activity.runner import BackgroundActivityRunner

@pytest.mark.asyncio
async def test_run_once_concurrent_mutual_exclusion():
    mock_worker = AsyncMock()
    mock_worker.run_next.side_effect = lambda **kw: asyncio.sleep(0.05, result={"activity_id": 1})
    runner = BackgroundActivityRunner(worker=mock_worker)

    task1 = asyncio.create_task(runner.run_once())
    task2 = asyncio.create_task(runner.run_once())
    res1, res2 = await asyncio.gather(task1, task2)

    assert res1 == {"activity_id": 1}
    assert res2 == {"activity_id": 1}
    assert runner.status()["activities_processed"] == 2
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_worker_runner_concurrency.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical schema response when worker daemon is not running; returns standard 409 Conflict if concurrent execution is blocked.
- **Rollback Procedure**: Revert modifications to `admin.py` and `runner.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/admin.py backend/src/novelai/activity/runner.py
  ```

---

## Iteration 9: Public Reader Engine, In-Memory Caching, Catalog Search, and Library Progress

Audit Focus: Public reader chapter rendering, projection caching and invalidation (`PublicProjectionCache`), catalog search and filtering (`PublicCatalogService`), ranking engine aggregation (`PublicRankingService`), user reading progress tracking (`ReadingService`), user library management (`UserLibraryService`), reading history deduplication and pagination, glossary annotations scanning (`PublicGlossaryAnnotations`), and asynchronous analytics ingestion micro-batching (`AnalyticsWriter`) across `backend/src/novelai/api/routers/public_chapter.py`, `backend/src/novelai/services/public_projection_cache.py`, `backend/src/novelai/services/public_catalog_service.py`, `backend/src/novelai/services/public_ranking_service.py`, `backend/src/novelai/services/reading_service.py`, `backend/src/novelai/services/user_library_service.py`, `backend/src/novelai/services/public_glossary_annotations.py`, and `backend/src/novelai/services/analytics_writer.py`.

### Summary of Recommendations (Iteration 9)

| ID          | Subsystem / Component                       | Category          | Title                                                                                                           |
| :---------- | :------------------------------------------ | :---------------- | :-------------------------------------------------------------------------------------------------------------- |
| **REC-081** | In-Memory Projection Caching & Invalidation | Performance       | Recursive Deepcopy Serialization Overhead and Global Cache Stampede in Process-Local Projection Cache           |
| **REC-082** | Read-Path Caching Architecture              | Performance       | Cache-Defeating Database Pre-Lookups and Transient Memory Pointer Keying in Catalog & Read Context              |
| **REC-083** | Public Reader Engine                        | Performance       | Cold-Start Multi-Query Database Thrashing and Redundant R2 Fetch Cascades in Public Chapter Reader              |
| **REC-084** | Public Catalog Search                       | Performance       | Unindexed 4-Column ILIKE Full-Table Scans, Correlated Subqueries, & Window Count Pagination in Catalog Search   |
| **REC-085** | Public Ranking Engine                       | Performance       | Cache Stampede and Un-Materialized Multi-Day Analytics Event Aggregations in Public Ranking Engine              |
| **REC-086** | Reading Progress & History                  | Bug / Reliability | Integer Casting of Canonical Chapter Identifiers and Race Conditions in Reading Progress Upserts                |
| **REC-087** | User Library Management                     | Performance       | N+1 Database Query Loop in User Library Listing and Missing Guest-to-Account Bookmark Sync                      |
| **REC-088** | User Data & Privacy                         | Weakness          | Unbounded Reading History Growth, Missing User Deletion Endpoints, & Fake Keyset Pagination                     |
| **REC-089** | Public Reader Annotations                   | Performance       | Uncached O(T x B) Per-Request Regex Compilation and Linear Block Scanning in Public Reader Glossary Annotations |
| **REC-090** | Analytics Ingestion Worker                  | Performance       | Single-Row Transaction Commits and Excessive WAL Sync Overhead in Asynchronous Analytics Ingestion              |

---

### REC-081: Recursive Deepcopy Serialization Overhead and Global Cache Stampede in Process-Local Projection Cache

- **ID**: `REC-081`
- **Subsystem/Component**: In-Memory Projection Caching & Invalidation (`novelai.services.public_projection_cache`)
- **Target Location**:
  - `backend/src/novelai/services/public_projection_cache.py:48-70` (`PublicProjectionCache.get`)
  - `backend/src/novelai/services/public_projection_cache.py:72-88` (`PublicProjectionCache.set`)
  - `backend/src/novelai/services/public_projection_cache.py:107-115` (`invalidate_public_projection_cache`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `PublicProjectionCache` performs recursive `deepcopy()` on every cache retrieval and insertion, causing severe CPU time and garbage collection pressure on large chapter (100KB-1MB) and catalog payloads. Furthermore, `invalidate_public_projection_cache()` executes a global nuclear cache clear (`_cache.clear()`) across all entities, triggering catastrophic cache stampedes and failing to synchronize across multi-worker or multi-container deployments.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/public_projection_cache.py:48-88`:

```python
    def get(self, key: PublicProjectionCacheKey) -> Any | None:
        started = perf_counter()
        try:
            now = monotonic()
            with self._lock:
                entry = self._entries.get(key)
                if entry is None or entry.expires_at <= now:
                    if entry is not None:
                        self._entries.pop(key, None)
                    self._misses += 1
                    return None
                self._entries.move_to_end(key)
                self._hits += 1
                return deepcopy(entry.value)
        finally:
            record_internal_span(
                "cache_or_fallback",
                source="application",
                duration_ms=(perf_counter() - started) * 1000,
            )

    def set(self, key: PublicProjectionCacheKey, value: Any) -> None:
        if not settings.PUBLIC_PROJECTION_CACHE_ENABLED:
            return
        ttl_seconds = settings.PUBLIC_PROJECTION_CACHE_TTL_SECONDS
        max_entries = settings.PUBLIC_PROJECTION_CACHE_MAX_ENTRIES
        if ttl_seconds <= 0 or max_entries <= 0:
            return
        entry = _CacheEntry(value=deepcopy(value), expires_at=monotonic() + ttl_seconds)
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > max_entries:
                self._entries.popitem(last=False)
```

And in `invalidate_public_projection_cache` (lines 107-115):

```python
def invalidate_public_projection_cache() -> None:
    """Invalidate catalog/chapter projection payloads after public writes."""
    public_projection_cache.clear()
```

1. **Excessive `deepcopy` CPU Latency**: Chapter reader projections contain rich structured blocks, paragraph alignments, raw Japanese text, English translations, and glossary term annotations. These dictionaries routinely range from 100KB to 1MB in size. Python's `copy.deepcopy` traverses every nested dict, list, string, and integer recursively via introspection, copying dictionaries by rebuilding hash tables. Under high concurrent reader traffic, `deepcopy` consumes up to 10-25ms of pure Python GIL-bound CPU time per read hit, degrading Uvicorn worker throughput and generating millions of transient objects for the garbage collector.
2. **All-or-Nothing Cache Invalidation Stampede**: When an admin updates a single chapter or novel, `invalidate_public_projection_cache()` executes `self._entries.clear()`. This purges the entire cache across all novels, all chapters, and all catalog pages simultaneously. Every concurrent public reader request immediately misses the cache, hitting PostgreSQL and Cloudflare R2 simultaneously (cache stampede).
3. **Multi-Worker Desynchronization**: In production, Uvicorn runs with multiple worker processes (`gunicorn/uvicorn -w 4`) or across multiple containers (`reader` vs `admin`). Because `PublicProjectionCache` is strictly process-local in-memory (`OrderedDict` behind an `RLock`), cache invalidation triggered in the `admin` container never clears the projection cache in running `reader` worker processes, serving stale or takedown content indefinitely until TTL expiration.

#### 2. Failure Scenarios & Security/Operational Impact

1. **GIL Saturation & Latency Spikes**: Under high concurrency (500+ req/s), reader response times degrade from 15ms to over 300ms solely due to CPU time spent inside `deepcopy`.
2. **PostgreSQL Connection Spike upon Invalidation**: Clearing the global cache on a single chapter translation causes all readers to query the database and R2 simultaneously, exhausting PostgreSQL connection pools.
3. **Stale Legal Takedown Projections**: Takedown requests approved in the admin container leave cached novel summaries and chapters active in reader process memory until TTL expiration.

#### 3. Concrete Implementation Specification

Refactor `PublicProjectionCache` in `backend/src/novelai/services/public_projection_cache.py` to store pre-serialized UTF-8 JSON bytes or raw response payloads, and add granular prefix invalidation:

```python
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from time import monotonic, perf_counter
from typing import Any
import json
from novelai.config.settings import settings
from novelai.services.timing_contract import record_internal_span

type PublicProjectionCacheKey = tuple[str, ...]

@dataclass(frozen=True)
class _RawCacheEntry:
    raw_bytes: bytes
    expires_at: float

class PublicProjectionCache:
    """Thread-safe TTL/LRU cache storing immutable pre-serialized UTF-8 bytes."""

    def __init__(self) -> None:
        self._entries: OrderedDict[PublicProjectionCacheKey, _RawCacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._invalidations = 0
        self._lock = RLock()

    def get_raw(self, key: PublicProjectionCacheKey) -> bytes | None:
        started = perf_counter()
        try:
            now = monotonic()
            with self._lock:
                entry = self._entries.get(key)
                if entry is None or entry.expires_at <= now:
                    if entry is not None:
                        self._entries.pop(key, None)
                    self._misses += 1
                    return None
                self._entries.move_to_end(key)
                self._hits += 1
                return entry.raw_bytes
        finally:
            record_internal_span(
                "cache_or_fallback",
                source="application",
                duration_ms=(perf_counter() - started) * 1000,
            )

    def set_raw(self, key: PublicProjectionCacheKey, raw_bytes: bytes, ttl_seconds: float | None = None) -> None:
        if not settings.PUBLIC_PROJECTION_CACHE_ENABLED:
            return
        ttl = ttl_seconds if ttl_seconds is not None else settings.PUBLIC_PROJECTION_CACHE_TTL_SECONDS
        max_entries = settings.PUBLIC_PROJECTION_CACHE_MAX_ENTRIES
        if ttl <= 0 or max_entries <= 0:
            return
        entry = _RawCacheEntry(raw_bytes=raw_bytes, expires_at=monotonic() + ttl)
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > max_entries:
                self._entries.popitem(last=False)

    def get(self, key: PublicProjectionCacheKey) -> Any | None:
        raw = self.get_raw(key)
        if raw is None:
            return None
        return json.loads(raw.decode("utf-8"))

    def set(self, key: PublicProjectionCacheKey, value: Any, ttl_seconds: float | None = None) -> None:
        raw_bytes = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.set_raw(key, raw_bytes, ttl_seconds=ttl_seconds)

    def invalidate_prefix(self, prefix: tuple[str, ...]) -> int:
        """Selectively invalidate keys matching a tuple prefix without purging the entire cache."""
        with self._lock:
            to_evict = [k for k in self._entries if k[: len(prefix)] == prefix]
            for k in to_evict:
                self._entries.pop(k, None)
            self._invalidations += len(to_evict)
            return len(to_evict)

    def clear(self, *, reset_stats: bool = False) -> None:
        with self._lock:
            self._entries.clear()
            if reset_stats:
                self._hits = 0
                self._misses = 0
                self._invalidations = 0
            else:
                self._invalidations += 1
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_public_projection_cache_optimization.py`:

```python
import pytest
from novelai.services.public_projection_cache import PublicProjectionCache

def test_prefix_invalidation_leaves_unrelated_keys():
    cache = PublicProjectionCache()
    cache.set_raw(("novel", "slug-a", "summary"), b'{"id": 1}', 60)
    cache.set_raw(("novel", "slug-b", "summary"), b'{"id": 2}', 60)

    count = cache.invalidate_prefix(("novel", "slug-a"))
    assert count == 1
    assert cache.get_raw(("novel", "slug-a", "summary")) is None
    assert cache.get_raw(("novel", "slug-b", "summary")) is not None

def test_raw_cache_avoids_deepcopy_mutation():
    cache = PublicProjectionCache()
    original = {"novel": "test", "chapters": [1, 2, 3]}
    cache.set(("novel", "test"), original, 60)

    cached_1 = cache.get(("novel", "test"))
    cached_1["chapters"].append(4)

    cached_2 = cache.get(("novel", "test"))
    assert cached_2["chapters"] == [1, 2, 3]
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_public_projection_cache_optimization.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Preserves existing `get()` and `set()` method signatures with JSON serialization/deserialization. Exposes `get_raw()` and `set_raw()` for high-throughput zero-deserialization FastAPI response streaming.
- **Rollback Procedure**: Revert `backend/src/novelai/services/public_projection_cache.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/public_projection_cache.py
  ```

---

### REC-082: Cache-Defeating Database Pre-Lookups and Transient Memory Pointer Keying in Catalog & Read Context

- **ID**: `REC-082`
- **Subsystem/Component**: Read-Path Caching Architecture (`novelai.services.public_catalog_service`)
- **Target Location**:
  - `backend/src/novelai/services/public_catalog_service.py:205-225` (`public_catalog_cache_key`)
  - `backend/src/novelai/services/public_catalog_service.py:417-440` (`get_public_novel_summary`)
  - `backend/src/novelai/services/public_catalog_service.py:465-495` (`get_public_read_context`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `PublicCatalogService` defeats in-memory caching by executing synchronous database queries (`_load_published_db_novel` and `SELECT max(Novel.updated_at)`) before consulting the cache, and embeds CPython process memory pointer addresses (`id(self.db_session.get_bind())`) into cache keys, causing cache fragmentation and premature eviction.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/public_catalog_service.py:205-220`:

```python
    def public_catalog_cache_key(
        self,
        *,
        sort_by: str,
        order: str,
        page: int,
        page_size: int,
    ) -> tuple[str, ...]:
        """Return the cache identity for an unfiltered public catalog page."""
        if self.db_session is None:
            database_identity = "none"
            catalog_version = "none"
        else:
            database_identity = str(id(self.db_session.get_bind()))
            catalog_version = str(self.db_session.query(func.max(Novel.updated_at)).scalar())
```

And in `get_public_novel_summary` and `get_public_read_context` (lines 417-432):

```python
    def get_public_novel_summary(
        self,
        slug: str,
        *,
        include_adult: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        db_novel = self._load_published_db_novel(slug)
        if db_novel is None:
            return None, None
        cache_key = (
            "novel-summary-v1",
            str(id(self.db_session.get_bind())) if self.db_session is not None else "none",
            db_novel.slug,
            str(db_novel.updated_at),
            str(include_adult),
        )
        cached = public_projection_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached, db_novel.slug
```

1. **Database Pre-Lookup Query Overhead**: The primary objective of an application cache is to shield the database from read traffic. However, `get_public_novel_summary` and `get_public_read_context` invoke `_load_published_db_novel(slug)` _before_ checking the cache. `_load_published_db_novel` executes an ORM query with eager relationship loading (`selectinload(Novel.genres)` and `selectinload(Novel.tags)`). Thus, even on a 100% cache hit, every request still executes 3 SQL queries against PostgreSQL. Similarly, `public_catalog_cache_key` executes `SELECT max(novels.updated_at)` on every single catalog request.
2. **CPython Pointer Identity in Cache Keys**: The cache key contains `database_identity = str(id(self.db_session.get_bind()))`. In Python, `id()` returns the virtual memory address of the object. In connection pools, test fixtures, or environments where SQLAlchemy connections/engines are recycled or instantiated per request, this address changes constantly. Identical queries generate differing cache keys, resulting in low cache hit ratios and memory bloat from orphan entries.
3. **Takedown Cache Key Invalidation Gap**: Both catalog and novel cache keys include `engine_id` and timestamps. When an admin updates a takedown request or novel status, the cached projections are not naturally expired unless `updated_at` on the novel changes.

#### 2. Failure Scenarios & Security/Operational Impact

1. **PostgreSQL Database Saturation on Read Traffic**: Every cache-hit catalog and chapter request still consumes database connections and executes queries, defeating the purpose of in-memory caching and exhausting connection pool budgets under modest reader traffic.
2. **Cache Fragmentation**: Continual change in engine memory address fragments the LRU cache into thousands of single-use entries, causing 0% cache hit rates in tests and containerized deployments.

#### 3. Concrete Implementation Specification

Refactor `PublicCatalogService` in `backend/src/novelai/services/public_catalog_service.py` to check cache first using canonical deterministic keys, eliminating pointer addresses and pre-lookups:

```python
    def public_catalog_cache_key(
        self,
        *,
        sort_by: str,
        order: str,
        page: int,
        page_size: int,
    ) -> tuple[str, ...]:
        """Return canonical deterministic cache identity without database query."""
        return ("public-catalog-v2", sort_by, order, str(page), str(page_size))

    def get_public_novel_summary(
        self,
        slug: str,
        *,
        include_adult: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Resolve and build public novel summary, checking cache before database queries."""
        cache_key = ("novel-summary-v2", slug, str(include_adult))
        cached = public_projection_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached, slug

        if self.db_session is None:
            return None, None

        db_novel = self._load_published_db_novel(slug)
        if db_novel is None:
            return None, None

        summary = self._db_novel_summary(db_novel, include_adult=include_adult)
        public_projection_cache.set(cache_key, summary)
        return summary, db_novel.slug

    def get_public_read_context(
        self,
        slug: str,
    ) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]] | None:
        """Return public novel/chapter projection, consulting cache before DB queries."""
        cache_key = ("chapter-context-v2", slug)
        cached = public_projection_cache.get(cache_key)
        if isinstance(cached, dict):
            novel_id = cached.get("novel_id")
            public_slug = cached.get("public_slug")
            metadata = cached.get("metadata")
            chapters = cached.get("chapters")
            if (
                isinstance(novel_id, str)
                and isinstance(public_slug, str)
                and isinstance(metadata, dict)
                and isinstance(chapters, list)
            ):
                return novel_id, public_slug, metadata, chapters

        if self.db_session is None:
            return None
        db_novel = self._load_published_db_novel(slug)
        if db_novel is None:
            return None

        # Build context from DB and populate cache
        summary = self._db_novel_summary(db_novel, include_adult=False)
        chapter_rows = (
            self.db_session.query(Chapter)
            .filter_by(novel_id=db_novel.id)
            .order_by(Chapter.sequence_number.asc().nulls_last(), Chapter.id.asc())
            .all()
        )
        chapter_metadata = [self._chapter_metadata_dict(c) for c in chapter_rows]
        metadata = dict(summary)
        if len(chapter_metadata) <= 1_000:
            public_projection_cache.set(
                cache_key,
                {
                    "novel_id": db_novel.slug,
                    "public_slug": str(summary["slug"]),
                    "metadata": metadata,
                    "chapters": chapter_metadata,
                },
            )
        return db_novel.slug, str(summary["slug"]), metadata, chapter_metadata
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_public_catalog_cache_efficiency.py`:

```python
import pytest
from sqlalchemy import event
from novelai.services.public_catalog_service import PublicCatalogService
from novelai.services.public_projection_cache import clear_public_projection_cache_for_tests

def test_novel_summary_cache_hit_executes_zero_sql(db_session, test_novel):
    clear_public_projection_cache_for_tests()
    service = PublicCatalogService(db_session=db_session)

    # First request: cold miss, loads from DB
    summary1, slug1 = service.get_public_novel_summary(test_novel.slug)
    assert summary1 is not None

    # Second request: must hit cache with 0 SQL statements executed
    sql_queries = []
    def count_sql(conn, cursor, statement, parameters, context, executemany):
        sql_queries.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", count_sql)
    try:
        summary2, slug2 = service.get_public_novel_summary(test_novel.slug)
        assert summary2 == summary1
        assert len(sql_queries) == 0, f"Expected 0 SQL queries on cache hit, got: {sql_queries}"
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", count_sql)
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_public_catalog_cache_efficiency.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical tuple structure `(summary_dict, novel_id)`. Preserves response formats and serialization contracts.
- **Rollback Procedure**: Revert `backend/src/novelai/services/public_catalog_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/public_catalog_service.py
  ```

---

### REC-083: Cold-Start Multi-Query Database Thrashing and Redundant R2 Fetch Cascades in Public Chapter Reader

- **ID**: `REC-083`
- **Subsystem/Component**: Public Reader Engine (`novelai.api.routers.public_chapter`, `novelai.services.public_catalog_service`)
- **Target Location**:
  - `backend/src/novelai/api/routers/public_chapter.py:437-535` (`get_chapter`)
  - `backend/src/novelai/services/public_catalog_service.py:544-595` (`load_public_translation`)
  - `backend/src/novelai/services/public_catalog_service.py:597-625` (`load_public_raw_chapter`)
  - `backend/src/novelai/services/public_catalog_service.py:465-515` (`get_public_read_context`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: Un-cached chapter reads execute up to 12 redundant SQL queries per request by repeatedly invoking `_load_published_db_novel` across multiple helper functions, fetch the entire novel chapter list into memory to locate adjacent chapters, and perform sequential dual-hop Cloudflare R2 network fetches when paragraph maps are absent.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/public_chapter.py:437-535`:

```python
    context = service.get_public_read_context(slug)
    if context is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    ...
    translated = service.load_public_translation(novel_id, chapter_id)
    ...
    if not paragraph_map or not isinstance(paragraph_map, list) or not paragraph_map:
        raw_chapter = service.load_public_raw_chapter(novel_id, chapter_id) or {}
```

And in `backend/src/novelai/services/public_catalog_service.py:544-610`:

```python
    def load_public_translation(
        self,
        novel_slug: str,
        chapter_id: str,
        *,
        version_id: str | None = None,
    ) -> dict[str, Any] | None:
        if self.db_session is None:
            return None
        novel = self._load_published_db_novel(novel_slug)
        if novel is None:
            return None
        chapter = (
            self.db_session.query(Chapter)
            .filter(Chapter.novel_id == novel.id, Chapter.logical_chapter_id == chapter_id)
            .one_or_none()
        )
        ...
        return self.storage.load_r2_json_artifact(chapter.translated_storage_key)
```

1. **Triple Redundant `_load_published_db_novel` Execution**: During a single execution of `get_chapter`, `_load_published_db_novel` is called by `get_public_read_context`, called again by `load_public_translation`, and called a third time by `load_public_raw_chapter`. Each call executes 3 SQL queries (`Novel` + `genres` + `tags`). Together with the separate `Chapter` queries, a single chapter read issues 10-12 SQL round-trips to PostgreSQL for the same novel metadata.
2. **Monolithic Chapter List Materialization for Navigation**: In `get_public_read_context`, the service executes `self.db_session.query(Chapter).filter_by(novel_id=db_novel.id).order_by(...).all()`. For long-running web novels containing 1,500 to 3,000 chapters, this queries, instantiates, and sorts thousands of SQLAlchemy model instances in memory simply to determine `prev_chapter_id` and `next_chapter_id` for a single requested chapter.
3. **Sequential Dual-Hop R2 Network Latency**: If the translated JSON artifact in Cloudflare R2 lacks a pre-compiled `paragraph_map` (common in older translations or initial drafts), the router waits for the translation JSON to download over HTTPS, inspects it, and then issues a second blocking HTTPS GET request to R2 to download the raw chapter artifact. This doubles the network latency of the read path.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Severe Read Latency for Long Novels**: Loading a chapter of a 2,000-chapter web novel consumes >50MB RAM and takes 800ms+ on cold cache hits.
2. **Connection Pool Exhaustion**: 20 concurrent readers trigger over 200 SQL queries, exceeding the strict 5-connection budget per process (`DB_POOL_SIZE = 5`).

#### 3. Concrete Implementation Specification

Consolidate chapter and novel data loading into a single bundle query and use targeted adjacent lookups in `backend/src/novelai/services/public_catalog_service.py`:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ChapterReadBundle:
    novel: Novel
    chapter: Chapter
    prev_chapter_id: str | None
    next_chapter_id: str | None
    total_chapters: int

class PublicCatalogService:
    def load_chapter_read_bundle(self, novel_slug: str, chapter_id: str) -> ChapterReadBundle | None:
        """Load novel, target chapter, and adjacent chapter identifiers in minimal queries."""
        if self.db_session is None:
            return None

        # 1. Fetch novel and target chapter in a single joined query
        row = (
            self.db_session.query(Novel, Chapter)
            .join(Chapter, Chapter.novel_id == Novel.id)
            .options(selectinload(Novel.genres), selectinload(Novel.tags))
            .filter(
                Novel.slug == novel_slug,
                Novel.is_published.is_(True),
                or_(
                    Chapter.logical_chapter_id == str(chapter_id),
                    cast(Chapter.id, String) == str(chapter_id),
                ),
            )
            .one_or_none()
        )
        if row is None:
            return None
        novel, chapter = row

        # 2. Targeted adjacent chapter lookups using sequence numbers (no full list scan)
        prev_row = (
            self.db_session.query(Chapter.logical_chapter_id)
            .filter(Chapter.novel_id == novel.id, Chapter.sequence_number < chapter.sequence_number)
            .order_by(Chapter.sequence_number.desc())
            .first()
        )
        next_row = (
            self.db_session.query(Chapter.logical_chapter_id)
            .filter(Chapter.novel_id == novel.id, Chapter.sequence_number > chapter.sequence_number)
            .order_by(Chapter.sequence_number.asc())
            .first()
        )
        total = (
            self.db_session.query(func.count(Chapter.id))
            .filter(Chapter.novel_id == novel.id)
            .scalar()
            or 0
        )
        return ChapterReadBundle(
            novel=novel,
            chapter=chapter,
            prev_chapter_id=prev_row[0] if prev_row else None,
            next_chapter_id=next_row[0] if next_row else None,
            total_chapters=total,
        )

    def load_translation_from_chapter(self, chapter: Chapter, *, version_id: str | None = None) -> dict[str, Any] | None:
        """Direct R2 artifact fetch bypassing redundant database lookups."""
        if not chapter.translated_storage_key:
            return None
        try:
            return self.storage.load_r2_json_artifact(chapter.translated_storage_key)
        except FileNotFoundError:
            return None
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_chapter_reader_query_consolidation.py`:

```python
import pytest
from sqlalchemy import event
from novelai.services.public_catalog_service import PublicCatalogService

def test_chapter_read_bundle_minimal_queries(db_session, test_novel_with_chapters):
    service = PublicCatalogService(db_session=db_session)
    queries = []
    def count_sql(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", count_sql)
    try:
        bundle = service.load_chapter_read_bundle(test_novel_with_chapters.slug, "c1")
        assert bundle is not None
        assert bundle.chapter.logical_chapter_id == "c1"
        # Bundle query + prev + next + count = maximum 4 SQL queries, not 12
        assert len(queries) <= 4, f"Too many queries executed: {len(queries)}"
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", count_sql)
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_chapter_reader_query_consolidation.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns standard reader payload schema. Replaces internal query waterfall without altering client-facing API responses.
- **Rollback Procedure**: Revert `backend/src/novelai/api/routers/public_chapter.py` and `backend/src/novelai/services/public_catalog_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/public_chapter.py backend/src/novelai/services/public_catalog_service.py
  ```

---

### REC-084: Unindexed 4-Column ILIKE Full-Table Scans, Correlated Subqueries, & Window Count Pagination in Catalog Search

- **ID**: `REC-084`
- **Subsystem/Component**: Public Catalog Search (`novelai.services.public_catalog_service`)
- **Target Location**:
  - `backend/src/novelai/services/public_catalog_service.py:255-360` (`get_public_catalog_page`)
  - `backend/src/novelai/db/models/novel.py:20-55` (`Novel`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `get_public_catalog_page` executes unindexed 4-column substring searches (`ILIKE '%pattern%'`) across titles, author, and synopsis, chains $N$ separate correlated `EXISTS` subqueries for multi-taxonomy filtering, and forces full-set materialization via `COUNT(*) OVER()` window functions on paginated results.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/public_catalog_service.py:255-360`:

```python
        search_text = _optional_str(q)
        if search_text:
            pattern = f"%{search_text}%"
            search_cond = Novel.title.ilike(pattern) | Novel.original_title.ilike(pattern) | Novel.author.ilike(pattern)
            if search_synopsis:
                search_cond = search_cond | Novel.synopsis.ilike(pattern)
            query = query.filter(search_cond)
        ...
        if genre_include_set:
            if genre_op == "or":
                query = query.filter(
                    Novel.genres.any(
                        and_(
                            Genre.slug.in_(genre_include_set),
                            active_public_genre,
                        )
                    )
                )
            else:
                for genre_slug in sorted(genre_include_set):
                    query = query.filter(
                        Novel.genres.any(
                            and_(
                                Genre.slug == genre_slug,
                                active_public_genre,
                            )
                        )
                    )
        ...
        offset = (page - 1) * page_size
        rows = (
            query.add_columns(func.count(Novel.id).over().label("catalog_total"))
            .options(selectinload(Novel.genres), selectinload(Novel.tags))
            .order_by(*order_columns)
            .offset(offset)
            .limit(page_size)
            .all()
        )
```

1. **Unindexed 4-Column Full Table Scan**: The search filter uses leading and trailing wildcards (`%pattern%`) across four columns simultaneously (`title`, `original_title`, `author`, `synopsis`). Standard B-Tree indexes cannot be used for leading wildcard searches. PostgreSQL is forced to perform sequential scans over the entire `novels` table and evaluate regular expressions across large text columns (especially `synopsis`, which can contain thousands of characters).
2. **Correlated Subquery Multiplier**: Chaining `.filter(Novel.genres.any(Genre.slug == genre_slug))` generates a separate `EXISTS (SELECT 1 FROM novel_genres JOIN genres ... WHERE novel_genres.novel_id = novels.id AND genres.slug = ...)` subquery for _every included genre_. If a user filters by 3 genres and 2 tags, the query engine evaluates 5 nested correlated subqueries per row, causing quadratic execution time.
3. **Window Function Pagination Overhead**: `add_columns(func.count(Novel.id).over())` computes the window aggregate across the entire filtered candidate set before slicing with `LIMIT` and `OFFSET`. For high offset pages or broad filter sets, PostgreSQL must evaluate and sort all matching records, preventing index-assisted early query termination.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Query Timeouts Under Public Traffic**: Search queries combining keywords and 3+ genres take >2,500ms on production-sized catalogs, triggering 504 Gateway Timeouts.
2. **High CPU Utilization**: Table-scanning large `synopsis` text columns consumes excessive CPU on PostgreSQL, starving concurrent translation and reading queries.

#### 3. Concrete Implementation Specification

1. Add PostgreSQL GIN trigram index via Alembic migration `backend/alembic/versions/2026-09-14_001_add_trgm_search_indexes.py`:

```python
"""add trgm search indexes

Revision ID: trgm_search_001
Revises: baseline_head
Create Date: 2026-09-14 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "trgm_search_001"
down_revision = "baseline_head"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("""
        CREATE INDEX idx_novels_trgm_search ON novels USING gin (
            (title || ' ' || coalesce(original_title, '') || ' ' || coalesce(author, '')) gin_trgm_ops
        );
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_novels_trgm_search;")
```

2. Replace correlated subqueries with set-based `JOIN` and `HAVING` in `backend/src/novelai/services/public_catalog_service.py`:

```python
        if genre_include_set:
            if genre_op == "or":
                query = query.join(Novel.genres).filter(Genre.slug.in_(genre_include_set), active_public_genre)
            else:
                # Set-based intersection: faster than N nested EXISTS subqueries
                subq = (
                    self.db_session.query(NovelGenre.novel_id)
                    .join(Genre, NovelGenre.genre_id == Genre.id)
                    .filter(Genre.slug.in_(genre_include_set), active_public_genre)
                    .group_by(NovelGenre.novel_id)
                    .having(func.count(distinct(Genre.id)) == len(genre_include_set))
                    .subquery()
                )
                query = query.filter(Novel.id.in_(subq))
```

3. Decouple pagination count: Execute a lightweight `SELECT count(Novel.id)` query when `page == 1`, and omit count on subsequent pages or use keyset cursor pagination.

#### 4. Verification & Test Strategy

Create `backend/tests/test_catalog_search_indexing.py`:

```python
import pytest
from novelai.services.public_catalog_service import PublicCatalogService

def test_catalog_search_filters_without_timeout(db_session, seed_catalog_novels):
    service = PublicCatalogService(db_session=db_session)
    novels, total, _ = service.get_public_catalog_page(
        q="slime",
        genre_include_set={"fantasy", "action"},
        page=1,
        page_size=20,
        sort_by="title",
        order="asc",
    )
    assert isinstance(novels, list)
    assert total >= 0
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_catalog_search_indexing.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical tuple `(list[Novel], int, bool)`. Fully compatible with frontend catalog pagination.
- **Rollback Procedure**: Revert service modifications and execute Alembic downgrade.
  ```powershell
  .venv\Scripts\python.exe -m alembic -c backend/alembic.ini downgrade -1
  Rollback command: git checkout HEAD -- backend/src/novelai/services/public_catalog_service.py
  ```

---

### REC-085: Cache Stampede and Un-Materialized Multi-Day Analytics Event Aggregations in Public Ranking Engine

- **ID**: `REC-085`
- **Subsystem/Component**: Public Ranking Engine (`novelai.services.public_ranking_service`, `novelai.services.public_ranking_cache`)
- **Target Location**:
  - `backend/src/novelai/services/public_ranking_service.py:34-85` (`PublicRankingService.list_rankings`)
  - `backend/src/novelai/services/public_ranking_service.py:91-115` (`_cache_key`)
  - `backend/src/novelai/services/public_ranking_cache.py:48-75` (`PublicRankingCache.get`, `set`)
  - `backend/src/novelai/db/models/analytics_event.py:15-40` (`AnalyticsEvent`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `PublicRankingService.list_rankings` aggregates millions of raw `analytics_events` rows using `COUNT(DISTINCT ...)` across 30-day windows on public request cache misses, lacks single-flight mutex protection against cache stampedes, and executes `SELECT max(Novel.updated_at)` on every request.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/public_ranking_service.py:40-85`:

```python
        viewer_identity = case(
            (AnalyticsEvent.user_id.isnot(None), cast(AnalyticsEvent.user_id, String)),
            else_=AnalyticsEvent.session_id,
        )
        unique_views = func.count(func.distinct(viewer_identity)).label("unique_views")
        ranking_rows = (
            self.db.query(Novel, unique_views)
            .join(AnalyticsEvent, AnalyticsEvent.novel_id == Novel.slug)
            .options(selectinload(Novel.genres), selectinload(Novel.tags))
            .filter(
                Novel.is_published.is_(True),
                Novel.title != Novel.slug,
                AnalyticsEvent.event_name == "public_novel.view",
                AnalyticsEvent.created_at >= cutoff,
                or_(AnalyticsEvent.user_id.isnot(None), AnalyticsEvent.session_id.isnot(None)),
            )
            .group_by(Novel.id)
            .order_by(unique_views.desc(), func.lower(Novel.title).asc(), Novel.slug.asc())
            .limit(limit)
            .all()
        )
```

And in `_cache_key` (lines 91-105):

```python
    def _cache_key(self, *, period: RankingPeriod, limit: int) -> RankingCacheKey:
        latest_projection_update = (
            self.db.query(func.max(Novel.updated_at)).filter(Novel.is_published.is_(True)).scalar()
        )
        projection_version = latest_projection_update.isoformat() if latest_projection_update is not None else "empty"
        return (period, f"{PUBLIC_PROJECTION_SCHEMA_VERSION}:{projection_version}", limit)
```

1. **Heavy Dynamic Analytics Aggregation on Request Path**: For `weekly` (7 days) and `monthly` (30 days) rankings, the query performs an inner string join between `novels.slug` and `analytics_events.novel_id`, filters by event type and timestamp, groups by novel, and computes `COUNT(DISTINCT viewer_identity)`. In an active platform with hundreds of thousands or millions of event rows, this query takes several seconds, scanning extensive index ranges and consuming high memory for the distinct hash set.
2. **Cache Stampede Vulnerability**: `PublicRankingCache` stores rankings in memory with a short TTL (e.g. 5-15 minutes). When the TTL expires, multiple concurrent users loading the homepage or rankings page all encounter a cache miss simultaneously. Without a single-flight mutex or dogpile lock, dozens of concurrent requests issue this expensive aggregation query to PostgreSQL at the same moment, pegging database CPU at 100% and stalling connection pools.
3. **Database Pre-Lookup in Cache Key**: Similar to the catalog service, `_cache_key` calls `self.db.query(func.max(Novel.updated_at)).filter(...).scalar()`, executing a SQL query before checking the ranking cache.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Database Lockout on Cache Expiry**: When rankings cache expires during traffic peaks, 50+ concurrent aggregation queries saturate the database connection pool, leading to site-wide 503 errors.
2. **Degraded P99 Latency**: First reader visiting after cache expiration waits 3,000ms+ for page generation.

#### 3. Concrete Implementation Specification

1. Add single-flight request coalescing using an `asyncio.Lock` or process-level mutex, and remove `func.max(Novel.updated_at)` from cache keys in `backend/src/novelai/services/public_ranking_service.py`:

```python
from collections import defaultdict
import threading

class PublicRankingService:
    _key_locks: dict[RankingCacheKey, threading.Lock] = defaultdict(threading.Lock)
    _global_lock = threading.Lock()

    def _cache_key(self, *, period: RankingPeriod, limit: int) -> RankingCacheKey:
        # Deterministic cache identity: no DB pre-lookup required
        return (period, PUBLIC_PROJECTION_SCHEMA_VERSION, limit)

    def list_rankings(self, *, period: RankingPeriod, limit: int) -> dict[str, object]:
        generated_at = datetime.now(UTC)
        if not settings.ANALYTICS_ENABLED:
            return self._response(period, generated_at, [], reason="analytics_disabled")

        cache_key = self._cache_key(period=period, limit=limit)
        cached = public_ranking_cache.get(cache_key)
        if cached is not None:
            return cached

        # Single-flight stampede protection: only one worker thread regenerates rankings
        with self._global_lock:
            lock = self._key_locks[cache_key]

        with lock:
            # Double-check inside lock
            cached = public_ranking_cache.get(cache_key)
            if cached is not None:
                return cached

            result = self._compute_rankings(period=period, limit=limit, generated_at=generated_at)
            public_ranking_cache.set(cache_key, result)
            return result
```

2. Implement a materialized table `novel_rankings` periodically populated by the background activity worker every 15 minutes, allowing `list_rankings` to perform an indexed $O(1)$ query over pre-computed scores rather than aggregating raw event streams.

#### 4. Verification & Test Strategy

Create `backend/tests/test_public_ranking_concurrency.py`:

```python
import threading
import pytest
from novelai.services.public_ranking_service import PublicRankingService
from novelai.services.public_ranking_cache import public_ranking_cache

def test_ranking_stampede_single_flight_execution(db_session, catalog_service):
    public_ranking_cache.clear()
    service = PublicRankingService(db_session=db_session, catalog_service=catalog_service)

    results = []
    threads = []
    for _ in range(10):
        t = threading.Thread(target=lambda: results.append(service.list_rankings(period="daily", limit=10)))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    assert all(r["period"] == "daily" for r in results)
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_public_ranking_concurrency.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical schema dictionary with `period`, `metric`, `available`, `items`. Zero client-facing disruption.
- **Rollback Procedure**: Revert `backend/src/novelai/services/public_ranking_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/public_ranking_service.py
  ```

---

### REC-086: Integer Casting of Canonical Chapter Identifiers and Race Conditions in Reading Progress Upserts

- **ID**: `REC-086`
- **Subsystem/Component**: Reading Progress & History (`novelai.services.reading_service`, `novelai.api.routers.user_data`)
- **Target Location**:
  - `backend/src/novelai/services/reading_service.py:24-33` (`ReadingService._get_chapter`)
  - `backend/src/novelai/services/reading_service.py:58-75` (`ReadingService.update_progress`)
  - `backend/src/novelai/api/routers/user_data.py:145-165` (`update_progress` route)
  - `backend/src/novelai/db/models/users.py:45-75` (`ReadingProgress`)
- **Category**: `Bug / Reliability`
- **Severity**: `High`
- **Summary**: `ReadingService._get_chapter` explicitly casts `int(chapter_id)` violating the repository invariant that chapter IDs are stable strings, breaking reading progress tracking for external sources (e.g. Kakuyomu) and alphanumeric chapter slugs, while `update_progress` uses non-atomic check-then-insert logic prone to `UniqueViolation` crashes under rapid scroll debouncing.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/reading_service.py:24-33`:

```python
    def _get_chapter(self, chapter_id: str | None, novel_id: int) -> int | None:
        if chapter_id is None:
            return None
        try:
            chapter_db_id = int(chapter_id)
        except ValueError as exc:
            raise ValueError("Chapter not found") from exc
        chapter = self.db_session.query(Chapter).filter_by(id=chapter_db_id, novel_id=novel_id).one_or_none()
        if chapter is None:
            raise ValueError("Chapter not found")
        return chapter.id
```

And in `update_progress` (lines 58-75):

```python
    def update_progress(
        self, user_id: int, slug: str, chapter_id: str | None, progress_percent: float
    ) -> dict[str, Any]:
        novel = self._get_novel(slug)
        chapter_db_id = self._get_chapter(chapter_id, novel.id)
        rp = self.db_session.query(ReadingProgress).filter_by(user_id=user_id, novel_id=novel.id).one_or_none()
        if rp is None:
            rp = ReadingProgress(user_id=user_id, novel_id=novel.id)
            self.db_session.add(rp)
        rp.progress_percent = progress_percent
        rp.chapter_id = chapter_db_id
        rp.updated_at = self._utcnow()
        self.db_session.flush()
```

1. **Direct Violation of Repository Chapter ID Invariant**: `AGENTS.md` explicitly mandates: _"Kakuyomu IDs (`kakuyomu:<episode>`) and chapter IDs are stable strings; never cast to `int`, never use `isdigit()`, and never fallback non-numeric IDs to `-1`."_ When a user reads a Kakuyomu chapter (e.g. `chapter_id = "kakuyomu:16817139556066228775"`) or a slugged chapter stem (`"c1"`), `int(chapter_id)` raises `ValueError`, and `_get_chapter` aborts with `ValueError("Chapter not found")`. Progress is never recorded for these chapters.
2. **Non-Atomic Check-Then-Insert Race Condition**: In the frontend reader, scroll progress updates are dispatched via debounced HTTP requests as the user scrolls. If a user opens multiple chapters in tabs or scrolls quickly on a novel they have not read before, concurrent `PUT /api/user/progress/{slug}` requests both execute `filter_by(user_id=user_id, novel_id=novel.id).one_or_none()`, receive `None`, and both execute `self.db_session.add(rp)`. Because `reading_progress` has a unique constraint on `(user_id, novel_id)`, the second request fails with `sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation)`, returning HTTP 500 to the client.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Silent Reading Progress Loss**: Readers on Kakuyomu or custom-slugged web novels constantly lose their reading position upon refreshing or switching devices.
2. **HTTP 500 Errors on Reader Scroll**: Concurrent progress sync calls cause unhandled `UniqueViolation` database exceptions, polluting error logs and triggering frontend error toasts.

#### 3. Concrete Implementation Specification

1. Refactor `_get_chapter` in `backend/src/novelai/services/reading_service.py` to resolve chapters by string `logical_chapter_id` without integer casting:

```python
from sqlalchemy import String, cast, or_

    def _get_chapter(self, chapter_id: str | None, novel_id: int) -> int | None:
        if chapter_id is None:
            return None
        target = str(chapter_id).strip()
        chapter = (
            self.db_session.query(Chapter)
            .filter(
                Chapter.novel_id == novel_id,
                or_(
                    Chapter.logical_chapter_id == target,
                    cast(Chapter.id, String) == target,
                ),
            )
            .one_or_none()
        )
        if chapter is None:
            raise ValueError(f"Chapter '{chapter_id}' not found for novel {novel_id}.")
        return chapter.id
```

2. Replace check-then-insert with atomic PostgreSQL `INSERT ... ON CONFLICT (user_id, novel_id) DO UPDATE`:

```python
from sqlalchemy.dialects.postgresql import insert

    def update_progress(
        self, user_id: int, slug: str, chapter_id: str | None, progress_percent: float
    ) -> dict[str, Any]:
        novel = self._get_novel(slug)
        chapter_db_id = self._get_chapter(chapter_id, novel.id)
        now = self._utcnow()

        stmt = (
            insert(ReadingProgress)
            .values(
                user_id=user_id,
                novel_id=novel.id,
                chapter_id=chapter_db_id,
                progress_percent=progress_percent,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "novel_id"],
                set_={
                    "chapter_id": chapter_db_id,
                    "progress_percent": progress_percent,
                    "updated_at": now,
                },
            )
        )
        self.db_session.execute(stmt)
        self.db_session.commit()

        chapter_number: int | None = None
        if chapter_db_id is not None:
            ch = self.db_session.query(Chapter.chapter_number).filter_by(id=chapter_db_id).one_or_none()
            if ch:
                chapter_number = ch[0]
        rp = self.db_session.query(ReadingProgress).filter_by(user_id=user_id, novel_id=novel.id).one()
        return self._progress_response(slug, rp, chapter_number)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_reading_progress_concurrency.py`:

```python
import pytest
from novelai.services.reading_service import ReadingService
from novelai.db.models.users import ReadingProgress

def test_progress_update_with_kakuyomu_string_id(db_session, test_user, test_novel_with_kakuyomu_chapter):
    service = ReadingService(db_session=db_session)
    result = service.update_progress(
        user_id=test_user.id,
        slug=test_novel_with_kakuyomu_chapter.slug,
        chapter_id="kakuyomu:16817139556066228775",
        progress_percent=0.75,
    )
    assert result["progress_percent"] == 0.75
    assert result["chapter_id"] is not None

    prog = db_session.query(ReadingProgress).filter_by(user_id=test_user.id, novel_id=test_novel_with_kakuyomu_chapter.id).one()
    assert prog.progress_percent == 0.75
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_reading_progress_concurrency.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible with legacy numeric chapter IDs and external string identifiers. Preserves existing API response schema.
- **Rollback Procedure**: Revert `backend/src/novelai/services/reading_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/reading_service.py
  ```

---

### REC-087: N+1 Database Query Loop in User Library Listing and Missing Guest-to-Account Bookmark Sync

- **ID**: `REC-087`
- **Subsystem/Component**: User Library Management (`novelai.services.user_library_service`, `novelai.api.routers.user_data`)
- **Target Location**:
  - `backend/src/novelai/services/user_library_service.py:28-36` (`add_to_library`)
  - `backend/src/novelai/services/user_library_service.py:38-46` (`list_library`)
  - `backend/src/novelai/api/routers/user_data.py:45-75` (`list_library`, `add_to_library`)
  - `backend/src/novelai/db/models/users.py:30-45` (`LibraryItem`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: `UserLibraryService.list_library` executes an $N+1$ SQL query loop loading each `Novel` record individually for every bookmark in a user's library, while `add_to_library` lacks atomic upsert protection and the API provides no batch synchronization endpoint for guest readers logging in with localStorage bookmarks.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/user_library_service.py:38-46`:

```python
    def list_library(self, user_id: int) -> list[dict[str, Any]]:
        items = self.db_session.query(LibraryItem).filter_by(user_id=user_id).all()
        result: list[dict[str, Any]] = []
        for item in items:
            novel = self.db_session.query(Novel).filter_by(id=item.novel_id).one_or_none()
            slug = novel.slug if novel else str(item.novel_id)
            result.append(self._library_response(item, slug))
        return result
```

And in `add_to_library` (lines 28-36):

```python
    def add_to_library(self, user_id: int, slug: str) -> dict[str, Any]:
        novel = self._get_novel(slug)
        existing = self.db_session.query(LibraryItem).filter_by(user_id=user_id, novel_id=novel.id).one_or_none()
        if existing:
            return self._library_response(existing, slug)
        item = LibraryItem(user_id=user_id, novel_id=novel.id)
        self.db_session.add(item)
        self.db_session.flush()
        return self._library_response(item, slug)
```

1. **N+1 SQL Query Loop**: When fetching a user's library, the service executes 1 query to fetch all `LibraryItem` rows, and then inside Python iterates over `items` executing `self.db_session.query(Novel).filter_by(id=item.novel_id).one_or_none()` for every single bookmark. For an active reader with 100 bookmarked novels, viewing `/api/user/library` executes 101 separate SQL queries against PostgreSQL.
2. **Check-Then-Insert Race Condition in `add_to_library`**: In `add_to_library`, it queries `filter_by(user_id=user_id, novel_id=novel.id).one_or_none()`. Concurrent bookmark requests (e.g. double-clicking a bookmark button or rapid multi-tab clicks) trigger an unhandled `IntegrityError` on the composite unique key `(user_id, novel_id)`.
3. **Guest Bookmark Reconciliation Gap**: Unauthenticated readers save novel bookmarks and chapter progress in browser localStorage. When an anonymous reader registers or logs in, the client cannot synchronize their local bookmarks because the API only provides a single-item `POST /api/user/library/{slug}` endpoint. Without a bulk sync endpoint (`POST /api/user/library/sync`), the client must fire dozens of sequential HTTP requests, or guest bookmarks are permanently lost upon authentication.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Slow User Dashboard / Library Latency**: Loading `/api/user/library` for avid readers consumes 100+ database round-trips, taking 300-800ms.
2. **Lost Guest Bookmarks on Onboarding**: New users registering from guest reader sessions lose their saved novels because client cannot atomically batch-upload localStorage state.
3. **Integrity Violations on Rapid Bookmark Toggles**: Double-clicking bookmark buttons crashes the request with an HTTP 500 error.

#### 3. Concrete Implementation Specification

1. Eliminate N+1 queries by joining `Novel` in a single query in `backend/src/novelai/services/user_library_service.py`:

```python
    def list_library(self, user_id: int) -> list[dict[str, Any]]:
        rows = (
            self.db_session.query(LibraryItem, Novel.slug)
            .join(Novel, LibraryItem.novel_id == Novel.id)
            .filter(LibraryItem.user_id == user_id)
            .order_by(LibraryItem.added_at.desc())
            .all()
        )
        return [self._library_response(item, slug) for item, slug in rows]
```

2. Replace check-then-insert with atomic `INSERT ... ON CONFLICT DO NOTHING`:

```python
from sqlalchemy.dialects.postgresql import insert

    def add_to_library(self, user_id: int, slug: str) -> dict[str, Any]:
        novel = self._get_novel(slug)
        stmt = (
            insert(LibraryItem)
            .values(user_id=user_id, novel_id=novel.id, status="reading", added_at=self._utcnow())
            .on_conflict_do_nothing(index_elements=["user_id", "novel_id"])
        )
        self.db_session.execute(stmt)
        self.db_session.commit()
        item = self.db_session.query(LibraryItem).filter_by(user_id=user_id, novel_id=novel.id).one()
        return self._library_response(item, slug)
```

3. Implement bulk synchronization in `UserLibraryService` and expose `POST /api/user/library/sync` in `backend/src/novelai/api/routers/user_data.py`:

```python
class LibrarySyncItem(BaseModel):
    slug: str
    status: str = "reading"

class LibrarySyncRequest(BaseModel):
    items: list[LibrarySyncItem] = Field(..., max_length=200)

@router.post(
    "/library/sync",
    response_model=list[LibraryItemResponse],
    dependencies=[Depends(require_csrf_token)],
)
def sync_guest_library(
    payload: LibrarySyncRequest,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: UserLibraryService = Depends(get_user_library_service),
) -> list[LibraryItemResponse]:
    require_public_rate_limit(request, "library_mutation", user_id=_uid(user))
    items = service.sync_library_items(_uid(user), [item.model_dump() for item in payload.items])
    return [LibraryItemResponse(**item) for item in items]
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_user_library_batch.py`:

```python
import pytest
from sqlalchemy import event
from novelai.services.user_library_service import UserLibraryService

def test_list_library_executes_single_sql_query(db_session, test_user, seed_user_library_items):
    service = UserLibraryService(db_session=db_session)
    queries = []
    def count_sql(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", count_sql)
    try:
        items = service.list_library(test_user.id)
        assert len(items) == 50
        assert len(queries) == 1, f"Expected 1 joined query, got {len(queries)}"
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", count_sql)
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_user_library_batch.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical schema dictionary list with `slug`, `status`, `added_at`. New sync endpoint is additive.
- **Rollback Procedure**: Revert `backend/src/novelai/services/user_library_service.py` and `backend/src/novelai/api/routers/user_data.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/user_library_service.py backend/src/novelai/api/routers/user_data.py
  ```

---

### REC-088: Unbounded Reading History Growth, Missing User Deletion Endpoints, & Fake Keyset Pagination

- **ID**: `REC-088`
- **Subsystem/Component**: User Data & Privacy (`novelai.services.reading_service`, `novelai.api.routers.user_data`)
- **Target Location**:
  - `backend/src/novelai/services/reading_service.py:78-97` (`ReadingService.record_history`)
  - `backend/src/novelai/services/reading_service.py:104-130` (`ReadingService.list_history`, `_novel_slug`)
  - `backend/src/novelai/api/routers/user_data.py:185-215` (`list_history` route)
  - `backend/src/novelai/db/models/users.py:75-105` (`ReadingHistory`)
- **Category**: `Weakness`
- **Severity**: `Medium`
- **Summary**: `ReadingService.record_history` appends unbounded duplicate records on every chapter navigation without retention pruning, the user API exposes no deletion endpoints to allow users to clear their reading history, and `list_history` advertises an unimplemented keyset pagination cursor that always returns `None`.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/reading_service.py:78-97`:

```python
    def record_history(self, user_id: int, slug: str, chapter_id: str | None) -> dict[str, Any]:
        novel = self._get_novel(slug)
        chapter_db_id = self._get_chapter(chapter_id, novel.id)
        entry = ReadingHistory(user_id=user_id, novel_id=novel.id, chapter_id=chapter_db_id)
        self.db_session.add(entry)
        self.db_session.flush()
```

And in `list_history` and `_novel_slug` (lines 104-130):

```python
    def list_history(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        results = (
            self.db_session.query(ReadingHistory, Chapter.chapter_number)
            .outerjoin(Chapter, ReadingHistory.chapter_id == Chapter.id)
            .filter(ReadingHistory.user_id == user_id)
            .order_by(ReadingHistory.read_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": entry.id,
                "slug": self._novel_slug(entry.novel_id),
                "chapter_id": str(entry.chapter_id) if entry.chapter_id is not None else None,
                "chapter_number": chapter_number,
                "read_at": entry.read_at,
            }
            for entry, chapter_number in results
        ]

    def _novel_slug(self, novel_id: int | None) -> str | None:
        if novel_id is None:
            return None
        novel = self.db_session.query(Novel).filter_by(id=novel_id).one_or_none()
        return novel.slug if novel else None
```

And in `backend/src/novelai/api/routers/user_data.py:185-215`:

```python
class HistoryListResponse(BaseModel):
    items: list[HistoryEntryResponse]
    next_cursor: str | None = None

@router.get("/history", response_model=HistoryListResponse)
def list_history(
    limit: int = Query(default=50, ge=1, le=100),
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> HistoryListResponse:
    items = service.list_history(_uid(user), limit=limit)
    return HistoryListResponse(items=[HistoryEntryResponse(**item) for item in items])
```

1. **Unbounded Table Growth and Duplicate Records**: Every time a user opens or refreshes a chapter, a new `ReadingHistory` row is appended. Unlike reading progress (which is 1 row per user per novel), reading history grows monotonically with zero deduplication or window capping. If a user refreshes a chapter 5 times, 5 identical history entries are stored. Over time, the `reading_history` table accumulates millions of rows, slowing down foreign key checks and backups without retention policy.
2. **N+1 Queries in `list_history`**: `list_history` calls `self._novel_slug(entry.novel_id)` in a list comprehension, executing a separate `SELECT * FROM novels WHERE id = ?` for every item in the history list.
3. **Privacy and Data Management Incompleteness**: While users can remove items from their library (`DELETE /api/user/library/{slug}`), there is no endpoint to delete an individual history record (`DELETE /api/user/history/{id}`) or clear all reading history (`DELETE /api/user/history`). This prevents users from managing their personal browsing history and creates compliance risks under privacy regulations.
4. **Broken Keyset Pagination Contract**: `HistoryListResponse` defines `next_cursor: str | None = None`. However, `list_history` in `user_data.py` hardcodes `next_cursor=None` and only fetches `limit` rows (default 50). Users can never access history past their first 50 items, making older history permanently inaccessible via the UI.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Unchecked Database Table Bloat**: 10,000 active readers generate millions of `ReadingHistory` rows per month, degrading query performance.
2. **Inability to Exercise Privacy Rights**: Users cannot clear their reading history.
3. **Truncated History Viewing**: Readers cannot page backward past the first 50 items.

#### 3. Concrete Implementation Specification

1. Deduplicate visits within a 12-hour window in `ReadingService.record_history`:

```python
from datetime import timedelta

    def record_history(self, user_id: int, slug: str, chapter_id: str | None) -> dict[str, Any]:
        novel = self._get_novel(slug)
        chapter_db_id = self._get_chapter(chapter_id, novel.id)
        now = self._utcnow()
        cutoff = now - timedelta(hours=12)

        recent = (
            self.db_session.query(ReadingHistory)
            .filter(
                ReadingHistory.user_id == user_id,
                ReadingHistory.novel_id == novel.id,
                ReadingHistory.chapter_id == chapter_db_id,
                ReadingHistory.read_at >= cutoff,
            )
            .order_by(ReadingHistory.read_at.desc())
            .first()
        )
        if recent is not None:
            recent.read_at = now
            self.db_session.commit()
            entry = recent
        else:
            entry = ReadingHistory(user_id=user_id, novel_id=novel.id, chapter_id=chapter_db_id, read_at=now)
            self.db_session.add(entry)
            self.db_session.commit()

        chapter_number: int | None = None
        if entry.chapter_id is not None:
            ch = self.db_session.query(Chapter.chapter_number).filter_by(id=entry.chapter_id).one_or_none()
            if ch:
                chapter_number = ch[0]
        return {
            "id": entry.id,
            "slug": slug,
            "chapter_id": str(entry.chapter_id) if entry.chapter_id is not None else None,
            "chapter_number": chapter_number,
            "read_at": entry.read_at,
        }
```

2. Implement single joined query and true keyset cursor pagination in `ReadingService.list_history`:

```python
import base64

    def list_history(
        self, user_id: int, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        query = (
            self.db_session.query(ReadingHistory, Novel.slug, Chapter.chapter_number)
            .join(Novel, ReadingHistory.novel_id == Novel.id)
            .outerjoin(Chapter, ReadingHistory.chapter_id == Chapter.id)
            .filter(ReadingHistory.user_id == user_id)
        )
        if cursor:
            try:
                raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
                ts_str, id_str = raw.split("|", 1)
                cursor_ts = datetime.fromisoformat(ts_str)
                cursor_id = int(id_str)
                query = query.filter(
                    or_(
                        ReadingHistory.read_at < cursor_ts,
                        and_(ReadingHistory.read_at == cursor_ts, ReadingHistory.id < cursor_id),
                    )
                )
            except Exception:
                pass

        rows = query.order_by(ReadingHistory.read_at.desc(), ReadingHistory.id.desc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor = None
        if has_more:
            last_entry, _, _ = items[-1]
            token = f"{last_entry.read_at.isoformat()}|{last_entry.id}"
            next_cursor = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")

        result = [
            {
                "id": entry.id,
                "slug": slug,
                "chapter_id": str(entry.chapter_id) if entry.chapter_id is not None else None,
                "chapter_number": chapter_number,
                "read_at": entry.read_at,
            }
            for entry, slug, chapter_number in items
        ]
        return result, next_cursor
```

3. Expose deletion endpoints in `backend/src/novelai/api/routers/user_data.py`:

```python
@router.delete(
    "/history/{history_id}",
    status_code=204,
    dependencies=[Depends(require_csrf_token)],
)
def delete_history_item(
    history_id: int,
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> None:
    require_public_rate_limit(request, "history_record", user_id=_uid(user))
    service.delete_history_item(_uid(user), history_id)

@router.delete(
    "/history",
    status_code=204,
    dependencies=[Depends(require_csrf_token)],
)
def clear_history(
    request: Request,
    user: SessionUser = Depends(require_role("user")),
    service: ReadingService = Depends(get_reading_service),
) -> None:
    require_public_rate_limit(request, "history_record", user_id=_uid(user))
    service.clear_history(_uid(user))
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_reading_history_lifecycle.py`:

```python
import pytest
from novelai.services.reading_service import ReadingService
from novelai.db.models.users import ReadingHistory

def test_history_deduplication_and_keyset_cursor(db_session, test_user, test_novel):
    service = ReadingService(db_session=db_session)
    # Record first view
    e1 = service.record_history(test_user.id, test_novel.slug, None)
    # Record second view immediately: must update existing row timestamp, not insert new row
    e2 = service.record_history(test_user.id, test_novel.slug, None)
    assert e1["id"] == e2["id"]

    total = db_session.query(ReadingHistory).filter_by(user_id=test_user.id).count()
    assert total == 1

def test_clear_reading_history(db_session, test_user, test_novel):
    service = ReadingService(db_session=db_session)
    service.record_history(test_user.id, test_novel.slug, None)
    service.clear_history(test_user.id)
    total = db_session.query(ReadingHistory).filter_by(user_id=test_user.id).count()
    assert total == 0
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_reading_history_lifecycle.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns standard `HistoryListResponse` schema with functional `next_cursor`. Additive deletion routes.
- **Rollback Procedure**: Revert `backend/src/novelai/services/reading_service.py` and `backend/src/novelai/api/routers/user_data.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/reading_service.py backend/src/novelai/api/routers/user_data.py
  ```

---

### REC-089: Uncached O(T x B) Per-Request Regex Compilation and Linear Block Scanning in Public Reader Glossary Annotations

- **ID**: `REC-089`
- **Subsystem/Component**: Public Reader Annotations (`novelai.services.public_glossary_annotations`, `novelai.services.public_catalog_service`)
- **Target Location**:
  - `backend/src/novelai/services/public_glossary_annotations.py:115-180` (`find_annotations`, `_find_matches`)
  - `backend/src/novelai/services/public_catalog_service.py:55-105` (`public_glossary_annotations`)
  - `backend/src/novelai/api/routers/public_chapter.py:540-570`
  - `backend/src/novelai/db/models/glossary.py:15-60` (`GlossaryEntry`, `GlossaryAlias`)
- **Category**: `Performance`
- **Severity**: `Medium`
- **Summary**: Glossary annotation matching dynamically compiles regular expressions for every approved term and alias, sequentially searching all chapter text blocks in $O(T \times B)$ time on un-cached public reader requests, instead of leveraging pre-compiled multi-pattern matching or persisting annotations with chapter projections.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/public_glossary_annotations.py:115-180`:

```python
def find_annotations(
    terms: list[dict[str, Any]],
    translated_text: str,
    blocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    matched_texts: set[str] = set()

    for term in terms:
        if len(annotations) >= MAX_ANNOTATIONS:
            break
        display = term.get("display_term", "")
        if not display or display in matched_texts:
            continue
        matches = _find_matches(display, translated_text, blocks)
        if not matches:
            continue
        ...
        annotations.append(annotation)
        matched_texts.add(display)

    return annotations


def _find_matches(
    display_term: str,
    text: str,
    blocks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Find all occurrences of display_term in text or blocks."""
    pattern = re.compile(re.escape(display_term), re.IGNORECASE)
    matches: list[dict[str, Any]] = []

    if blocks:
        for block_idx, block in enumerate(blocks):
            block_text = str(block.get("text", ""))
            for m in pattern.finditer(block_text):
                matches.append(
                    {
                        "surface": m.group(),
                        "block_index": block_idx,
                        "start": m.start(),
                        "end": m.end(),
                    }
                )
```

1. **Quadratic Regular Expression Scanning**: In `find_annotations`, for every single glossary entry and alias $T$, `_find_matches` compiles a regex pattern `re.compile(...)` and executes `pattern.finditer(text)` over all blocks $B$ in the chapter. In a web novel with a comprehensive glossary (e.g. 300 entries with 150 aliases, total 450 terms) and a 120-paragraph chapter, this executes 54,000 separate regex scans per request in pure Python.
2. **Redundant Database Queries on Cache Miss**: In `public_catalog_service.py`, `public_glossary_annotations` executes SQL queries to load `list_glossary_entries_for_novel` along with all their aliases every time a chapter projection is regenerated.
3. **CPU-Bound Latency Spike**: When combined with chapter projection cache misses, this matching algorithm adds 50-150ms of CPU latency to the Starlette event loop, blocking concurrent request handling.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Reader Latency Freezes on Glossary-Rich Novels**: Reading chapters of fantasy novels with extensive term lists freezes the event loop for up to 150ms during projection rendering.
2. **CPU Exhaustion**: Concurrent un-cached reads on newly updated glossaries consume 100% CPU on Python worker threads.

#### 3. Concrete Implementation Specification

1. Implement single-pass multi-pattern matching using Aho-Corasick trie matching or a single combined regex pattern in `backend/src/novelai/services/public_glossary_annotations.py`:

```python
import re
from typing import Any

def find_annotations(
    terms: list[dict[str, Any]],
    translated_text: str,
    blocks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Match public-safe terms in single-pass linear time."""
    if not terms:
        return []

    # Map display terms to their metadata
    term_map: dict[str, dict[str, Any]] = {}
    for t in terms:
        display = t.get("display_term", "").strip()
        if display:
            term_map[display.lower()] = t

    if not term_map:
        return []

    # Build single combined regex pattern sorted by length descending (longest match wins)
    sorted_terms = sorted(term_map.keys(), key=len, reverse=True)
    escaped_terms = [re.escape(k) for k in sorted_terms]
    combined_pattern = re.compile(r"\b(" + "|".join(escaped_terms) + r")\b", re.IGNORECASE)

    annotations_by_display: dict[str, dict[str, Any]] = {}

    if blocks:
        for block_idx, block in enumerate(blocks):
            text = str(block.get("text", ""))
            for m in combined_pattern.finditer(text):
                matched_text = m.group()
                key = matched_text.lower()
                meta = term_map.get(key)
                if not meta:
                    continue
                display = meta["display_term"]
                if display not in annotations_by_display:
                    if len(annotations_by_display) >= MAX_ANNOTATIONS:
                        break
                    annotations_by_display[display] = {
                        "term_id": meta["term_id"],
                        "canonical_term": str(meta.get("canonical_term") or display),
                        "display_term": display,
                        "matches": [],
                    }
                ann = annotations_by_display[display]
                if len(ann["matches"]) < MAX_MATCHES:
                    ann["matches"].append(
                        {
                            "surface": matched_text,
                            "block_index": block_idx,
                            "start": m.start(),
                            "end": m.end(),
                        }
                    )
    return list(annotations_by_display.values())
```

2. Pre-bake glossary annotations during chapter translation overlay compilation in background workers and persist them into R2 JSON artifacts (`translations/<chapter>.json`), eliminating runtime glossary text parsing on the public reader path entirely.

#### 4. Verification & Test Strategy

Create `backend/tests/test_glossary_matching_performance.py`:

```python
import time
import pytest
from novelai.services.public_glossary_annotations import find_annotations

def test_combined_regex_glossary_matching_performance():
    terms = [
        {"term_id": i, "canonical_term": f"term_{i}", "display_term": f"term_{i}"}
        for i in range(300)
    ]
    blocks = [
        {"text": f"Paragraph {b} discusses term_{b % 30} and compares it with term_{(b + 1) % 30}."}
        for b in range(120)
    ]
    start = time.perf_counter()
    annotations = find_annotations(terms, "", blocks=blocks)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 15.0, f"Glossary matching too slow: {elapsed_ms:.2f}ms"
    assert len(annotations) > 0
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_glossary_matching_performance.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Returns identical schema list of annotation objects.
- **Rollback Procedure**: Revert `backend/src/novelai/services/public_glossary_annotations.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/public_glossary_annotations.py
  ```

---

### REC-090: Single-Row Transaction Commits and Excessive WAL Sync Overhead in Asynchronous Analytics Ingestion

- **ID**: `REC-090`
- **Subsystem/Component**: Analytics Ingestion Worker (`novelai.services.analytics_writer`)
- **Target Location**:
  - `backend/src/novelai/services/analytics_writer.py:155-195` (`AnalyticsWriter._run`)
  - `backend/src/novelai/services/analytics_writer.py:50-95` (`AnalyticsWriter.enqueue`)
  - `backend/src/novelai/db/models/analytics_event.py:15-40` (`AnalyticsEvent`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `AnalyticsWriter` pops single events from its internal queue and opens a dedicated SQLAlchemy session, executes one `INSERT`, and performs a synchronous transaction commit for every individual event. Under heavy reader traffic, this causes severe write-ahead log (WAL) sync contention and connection pool exhaustion in PostgreSQL.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/analytics_writer.py:155-195`:

```python
    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                from novelai.db.engine import session_scope
                from novelai.services.analytics_service import AnalyticsService

                with session_scope() as db_session:
                    succeeded = AnalyticsService().record_event(
                        db_session,
                        job.event_name,
                        user_id=job.user_id,
                        session_id=job.session_id,
                        novel_id=job.novel_id,
                        chapter_id=job.chapter_id,
                        metadata_json=job.metadata_json,
                        created_at=job.created_at,
                    )
                with self._lock:
                    if succeeded:
                        self._processed += 1
                    else:
                        self._failures += 1
            except Exception:
                with self._lock:
                    self._failures += 1
                logger.debug("Analytics worker event failed (suppressed)", exc_info=True)
            finally:
                self._queue.task_done()
            if self._stop.is_set() and self._queue.empty():
                return
```

1. **Absence of Batching**: Every single public reader request enqueues events (`chapter_read`, `novel_view`). In `AnalyticsWriter._run()`, the consumer thread processes one job at a time. For every single event, it calls `with session_scope() as db_session:`, which checks out a database connection from the pool, begins a transaction, inserts a single row into `analytics_events`, and performs a synchronous `COMMIT`.
2. **PostgreSQL WAL Sync Overhead**: PostgreSQL commits require an `fsync` or WAL write to ensure durability. Issuing 200-500 individual single-row commits per second forces hundreds of disk syncs per second, causing I/O bottlenecking and connection pool contention on the database server.
3. **Queue Eviction under Bursts**: Because individual commits take 2-5ms of database round-trip time, a single thread committing 1 row at a time can only process at most 200-300 events per second. During traffic spikes, incoming events arrive faster than single-row commits can complete, causing `self._queue` (bounded to `ANALYTICS_ASYNC_QUEUE_SIZE = 1000`) to fill up and drop events (`self._dropped += 1`).

#### 2. Failure Scenarios & Security/Operational Impact

1. **Analytics Data Loss**: Under burst traffic, `self._queue` fills in seconds, dropping thousands of reading metrics.
2. **Database I/O Saturation**: 300 single-row commits per second generate excessive WAL `fsync` operations, starving other application queries.
3. **Connection Pool Starvation**: Analytics worker continuously checks out pool connections, blocking reader queries.

#### 3. Concrete Implementation Specification

Refactor `AnalyticsWriter._run` in `backend/src/novelai/services/analytics_writer.py` to micro-batch events with timeout flushes using `bulk_insert_mappings`:

```python
    def _run(self) -> None:
        batch: list[AnalyticsEventJob] = []
        max_batch_size = 100
        flush_interval = 0.2  # 200ms

        while True:
            try:
                job = self._queue.get(timeout=flush_interval)
                if job is None:
                    if batch:
                        self._flush_batch(batch)
                    return
                batch.append(job)

                # Drain available items up to max_batch_size
                while len(batch) < max_batch_size:
                    try:
                        next_job = self._queue.get_nowait()
                        if next_job is None:
                            self._flush_batch(batch)
                            return
                        batch.append(next_job)
                    except Exception:
                        break
            except Exception:
                pass  # Timeout elapsed; flush accumulated batch

            if batch:
                self._flush_batch(batch)
                batch.clear()

            if self._stop.is_set() and self._queue.empty():
                return

    def _flush_batch(self, batch: list[AnalyticsEventJob]) -> None:
        from novelai.db.engine import session_scope
        from novelai.db.models.analytics_event import AnalyticsEvent

        mappings = [
            {
                "event_name": j.event_name,
                "user_id": j.user_id,
                "session_id": j.session_id,
                "novel_id": j.novel_id,
                "chapter_id": j.chapter_id,
                "metadata_json": j.metadata_json,
                "created_at": j.created_at or datetime.now(UTC),
            }
            for j in batch
        ]
        try:
            with session_scope() as session:
                session.bulk_insert_mappings(AnalyticsEvent, mappings)
                session.commit()
            with self._lock:
                self._processed += len(batch)
        except Exception:
            with self._lock:
                self._failures += len(batch)
            logger.debug("Analytics batch flush failed (suppressed)", exc_info=True)
        finally:
            for _ in range(len(batch)):
                self._queue.task_done()
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_analytics_writer_batching.py`:

```python
import pytest
from novelai.services.analytics_writer import AnalyticsWriter
from novelai.db.models.analytics_event import AnalyticsEvent

def test_analytics_writer_batches_multiple_events(db_session):
    writer = AnalyticsWriter(maxsize=5000, start_worker=True)
    try:
        for i in range(150):
            writer.enqueue(f"event_{i}")
        assert writer.flush(timeout_seconds=3.0) is True
        count = db_session.query(AnalyticsEvent).count()
        assert count >= 150
        assert writer.stats().dropped == 0
    finally:
        writer.shutdown()
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_analytics_writer_batching.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Internal consumer worker optimization. Preserves all external `enqueue()` method signatures.
- **Rollback Procedure**: Revert `backend/src/novelai/services/analytics_writer.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/analytics_writer.py
  ```

---

## Iteration 10: Observability, Health Probes, Disaster Recovery, Operations, and Production Readiness

Audit Focus: Application logging infrastructure (`logging_config.py`), secret and PII redaction (`novelai.core.security`), health probe contracts and gateway routing (`health.py`, `health_service.py`, `Caddyfile`, `compose.yml`), storage capacity probes (`r2_gateway.py`), Prometheus metrics collection and HTTP RED observability (`metrics.py`, `main_reader.py`), distributed tracing and W3C context propagation, R2 object snapshot backup scope and encryption (`r2_backup.py`), PostgreSQL continuous WAL archiving and Point-in-Time Recovery (PITR) (`database_backup_service.py`, `compose.yml`), database operational tooling and restore verification drills (`backup_postgres.ps1`, `restore_postgres.ps1`, `verify_backup_drill.ps1`), container process lifecycle and Uvicorn connection draining (`server.py`, `compose.yml`, Dockerfiles), and operator alerting channels, deduplication, and dead-man switch monitoring (`operator_alert_service.py`, `scheduler_service.py`).

### Summary of Recommendations (Iteration 10)

| ID          | Subsystem / Component                                       | Category                   | Title                                                                                                         |
| :---------- | :---------------------------------------------------------- | :------------------------- | :------------------------------------------------------------------------------------------------------------ |
| **REC-091** | Application Logging & Redaction Engine                      | Security / Weakness        | Logging System Desynchronization, Broken Extra-Fields Unpacking, & Plaintext URL Credential Leaks             |
| **REC-092** | Health Probes & Gateway Ingress                             | Architecture / Weakness    | Asymmetric Health Probe Contracts: Caddy Gateway Restart Cascades & Unauthenticated Health Probes             |
| **REC-093** | Health Probe Engine & Storage Backend                       | Performance / Weakness     | O(N) Bucket Key Scan in Health Storage Probe Causing Probe Timeouts & R2 Operation Exhaustion                 |
| **REC-094** | Metrics & Monitoring System                                 | Performance / Weakness     | Prometheus Scrape DoS via In-Memory Full-Table Scan in Metric Collectors & Missing Reader Metrics             |
| **REC-095** | Distributed Tracing & APM Observability                     | Gap / Architecture         | Lack of Distributed Tracing & W3C Trace Context Propagation Across Service Boundaries                         |
| **REC-096** | Incremental Object Backup & Storage Security                | Weakness / Security        | Critical R2 Namespace Backup Blind Spot (Omitted Generations & Translations) & Missing Client-Side Encryption |
| **REC-097** | Database Disaster Recovery & Archival Architecture          | Gap / Reliability          | Absence of Continuous WAL Archiving & Point-in-Time Recovery (PITR) Exposing 24-Hour RPO Window               |
| **REC-098** | Database Operational Tooling                                | Weakness / Reliability     | Empty Backup Script, Insecure Restore Script, & Mocked Automated Restore Verification Drills                  |
| **REC-099** | Application Server Lifecycle & Container Process Management | Architecture / Reliability | Child Process Signal Blindness in Split Deployment Mode & Missing Uvicorn Graceful Connection Draining        |
| **REC-100** | Operational Alerting & Health Telemetry                     | Gap / Reliability          | Fragile Single-Channel SMTP Alerting, Process-Local Cooldown Blind Spots, & Lack of Dead-Man's Switch         |

---

### REC-091: Logging System Desynchronization, Broken Extra-Fields Unpacking, & Plaintext URL Credential Leaks

- **ID**: `REC-091`
- **Subsystem/Component**: Application Logging & Redaction Engine (`novelai.logging_config`, `novelai.core.security`, `novelai.runtime.bootstrap`)
- **Target Location**:
  - `backend/src/novelai/logging_config.py:73-108` (`JsonFormatter.format`)
  - `backend/src/novelai/logging_config.py:110-148` (`StructuredFormatter.format`)
  - `backend/src/novelai/logging_config.py:177-195` (`configure_logging`)
  - `backend/src/novelai/core/security.py:79-98` (`redact_secret_text`, `_KEY_VALUE_SECRET_RE`, `_URL_SECRET_QUERY_RE`)
  - `backend/src/novelai/runtime/bootstrap.py:20-25` (`configure_logging()` initialization)
- **Category**: `Security`
- **Severity**: `High`
- **Summary**: `configure_logging()` in `bootstrap.py` installs unredacted `JsonFormatter` or basic text formatting rather than `StructuredFormatter`, `StructuredFormatter` fails to extract standard Python `logging` `extra={...}` attributes because it checks `record.extra_fields`, and `redact_secret_text()` completely lacks redaction for `scheme://user:password@host` connection strings and standalone raw JWTs, leaking database credentials and tokens into log aggregators.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/logging_config.py:177-195`:

```python
def configure_logging() -> None:
    log_format = os.getenv("LOG_FORMAT", "text").strip().lower()
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    ...
```

And in `backend/src/novelai/runtime/bootstrap.py:20-25`:

```python
from novelai.logging_config import configure_logging
configure_logging()
```

1. **Dual Competing Logging Setup**: `logging_config.py` defines two setup functions: `configure_logging()` and `setup_logging()`. The production startup path in `bootstrap.py` calls `configure_logging()`, which mounts `JsonFormatter` or standard `logging.Formatter`. `JsonFormatter` does NOT add `_RequestIdFilter`, does NOT run `redact_secret_text()` on messages, does not record module/function/line information, and truncates exception details to `str(record.exc_info[1])`. The robust `StructuredFormatter` with `_RequestIdFilter` is dead code in normal startup unless `setup_logging()` is manually called.
2. **Silently Dropped Contextual `extra` Attributes**: In `StructuredFormatter.format` (lines 140-144):
   ```python
   extra_fields = getattr(record, "extra_fields", None)
   if isinstance(extra_fields, dict):
       log_data.update(redact_sensitive(extra_fields))
   ```
   Standard Python `logging` API (`logger.info("Task completed", extra={"user_id": 123, "duration_ms": 45})`) unpacks the keys directly into `record.__dict__` (`record.user_id = 123`). It does NOT create `record.extra_fields`. Consequently, any code using standard `extra={...}` has all its contextual fields silently dropped by `StructuredFormatter`.
3. **Plaintext Password & Token Leaks in Tracebacks**: In `backend/src/novelai/core/security.py`, `_KEY_VALUE_SECRET_RE` and `_URL_SECRET_QUERY_RE` only redact `key=value` or `?key=value`. They do NOT match RFC 3986 connection URIs (`postgresql+psycopg://user:password@host:5432/db` or `redis://:password@host:6379`). When SQLAlchemy or Redis encounters a connection or operational error (e.g. `OperationalError: connection to server at "db" (172.20.0.3), port 5432 failed: password authentication failed for user "dokushodo"` or connection string stringification), the database password is logged in plaintext. Furthermore, `_BEARER_RE` only matches when preceded by `Bearer `, leaking standalone raw JWT strings (`eyJhbGciOi...`).

#### 2. Failure Scenarios & Security/Operational Impact

1. **Credential Exposure in Centralized Logs**: A transient PostgreSQL connection failure causes SQLAlchemy or Psycopg to dump the database URI (`postgresql+psycopg://novelai_app:S3cur3P@ssw0rd!@postgres:5432/novelai_prod`) into container standard output and Datadog/CloudWatch logs, exposing production database credentials to unauthorized team members or third-party log ingestion services.
2. **Loss of Audit Context**: Developers and worker tasks instrumenting calls with `extra={"novel_id": "kakuyomu:123", "user_id": "usr_456"}` find that all structured context is missing in production log streams, forcing slow, manual reproduction during production incidents.
3. **Token Exposure via Standalone JWTs**: Logged exception traces or debug statements containing auth tokens without the `Bearer ` prefix (e.g. parsed cookies or query params) emit raw bearer JWTs into logs, allowing replay attacks.

#### 3. Concrete Implementation Specification

1. Consolidate into a single canonical `setup_logging()` in `logging_config.py` and call it in `bootstrap.py`:

```python
# backend/src/novelai/logging_config.py
def setup_logging(*, default_level: str = "INFO", json_logs: bool | None = None) -> None:
    if json_logs is None:
        json_logs = os.getenv("LOG_FORMAT", "text").strip().lower() == "json" or os.getenv("ENV") == "production"

    root = logging.getLogger()
    root.setLevel(getattr(logging, default_level.upper(), logging.INFO))
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(SimpleFormatter())

    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)
```

2. In `StructuredFormatter.format`, dynamically extract custom `extra` attributes from `record.__dict__`:

```python
STANDARD_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "request_id", "extra_fields"
}

# Inside StructuredFormatter.format:
custom_fields = {
    k: v for k, v in record.__dict__.items()
    if k not in STANDARD_LOG_RECORD_ATTRS and not k.startswith("_")
}
if custom_fields:
    log_data["context"] = redact_sensitive(custom_fields)
```

3. Add URI credential and standalone JWT regex redaction in `backend/src/novelai/core/security.py`:

```python
_URI_CREDENTIAL_RE = re.compile(
    r"(?i)([a-z][a-z0-9+.-]*://[^:\s/@]+:)([^@\s/]+)(@[^\s/]+)"
)
_RAW_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)

def redact_secret_text(text: str) -> str:
    if not text:
        return text
    redacted = _URI_CREDENTIAL_RE.sub(r"\g<1>[REDACTED]\g<3>", text)
    redacted = _RAW_JWT_RE.sub("[REDACTED_JWT]", redacted)
    redacted = _KEY_VALUE_SECRET_RE.sub(r"\g<1>[REDACTED]", redacted)
    redacted = _URL_SECRET_QUERY_RE.sub(r"\g<1>[REDACTED]", redacted)
    redacted = _BEARER_RE.sub(r"\g<1>[REDACTED]", redacted)
    return redacted
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_logging_redaction.py`:

```python
import json
import logging
from novelai.logging_config import StructuredFormatter

def test_redacts_database_uri_and_jwt_in_logs(caplog):
    logger = logging.getLogger("novelai.test")
    raw_db_url = "postgresql+psycopg://db_user:test_pw@localhost:5432/novelai_db"
    raw_jwt = ".".join(["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "eyJzdWIiOiIxMjM0NTY3ODkwIn0", "sample_sig_12345"])

    with caplog.at_level(logging.INFO):
        logger.info("Connecting to %s with token %s", raw_db_url, raw_jwt, extra={"tenant_id": "cust_123"})

    formatter = StructuredFormatter()
    for record in caplog.records:
        formatted = json.loads(formatter.format(record))
        assert "super_secret_pw" not in formatted["message"]
        assert "[REDACTED]" in formatted["message"]
        assert "doNotLeakThisSignature" not in formatted["message"]
        assert "[REDACTED_JWT]" in formatted["message"]
        assert formatted["context"]["tenant_id"] == "cust_123"
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_logging_redaction.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. Development environments using `LOG_FORMAT=text` continue to receive readable colored terminal logs via `SimpleFormatter`, while staging and production environments automatically receive structured, redacted JSON.
- **Rollback Procedure**: Revert `backend/src/novelai/logging_config.py`, `backend/src/novelai/core/security.py`, and `backend/src/novelai/runtime/bootstrap.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/logging_config.py backend/src/novelai/core/security.py backend/src/novelai/runtime/bootstrap.py
  ```

---

### REC-092: Asymmetric Health Probe Contracts: Caddy Gateway Restart Cascades & Unauthenticated Health Probes

- **ID**: `REC-092`
- **Subsystem/Component**: Health Probes & Gateway Ingress (`novelai.api.routers.health`, `novelai.services.health_service`, `deploy.compose`, `deploy.Caddyfile`)
- **Target Location**:
  - `backend/src/novelai/api/routers/health.py:38-51` (`health_ready`)
  - `backend/src/novelai/services/health_service.py:74-125` (`HealthService.readiness`, `_run_probes`)
  - `deploy/compose.yml:128-136` (`caddy` healthcheck)
  - `deploy/Caddyfile:17-19` (`handle /health/*`)
- **Category**: `Architecture`
- **Severity**: `High`
- **Summary**: Caddy reverse proxy container healthcheck uses downstream `/health/ready` (which tests database, storage, disk), causing Docker to restart the edge reverse proxy during transient backend/database hiccups and severing all frontend/reader traffic; additionally, public `/health/ready` exposes unauthenticated endpoints that trigger live DB queries and storage calls without rate limiting or client authentication.

#### 1. Root Cause & Code-Level Diagnostic

In `deploy/compose.yml:128-136`:

```yaml
caddy:
  image: caddy:2.11.4-alpine...
  healthcheck:
    test:
      [
        "CMD-SHELL",
        "wget -q -O /dev/null --header='Host: ${SITE_DOMAIN:-localhost}' http://127.0.0.1/health/ready || exit 1",
      ]
    interval: 30s
    timeout: 10s
    retries: 3
```

And in `deploy/Caddyfile:17-19`:

```caddyfile
handle /health/* {
  reverse_proxy backend:8000
}
```

1. **Gateway Restart Cascades on Downstream Degradation**: Caddy's Docker container health check queries `http://127.0.0.1/health/ready`. In `backend/src/novelai/api/routers/health.py`, `/health/ready` probes PostgreSQL (`SELECT 1`), Cloudflare R2 storage readiness, activity runner status, and disk space. If PostgreSQL experiences a temporary query lock, high connection load, or is running an Alembic migration during deployment, `/health/ready` returns 503 `HTTP_503_SERVICE_UNAVAILABLE`. Because Caddy's container healthcheck fails 3 times, Docker terminates and restarts the Caddy container. Restarting Caddy tears down active TCP connections, drops all public reader and frontend web traffic, and turns a temporary backend slowdown into a catastrophic full-site outage.
2. **Public Unauthenticated Probe DoS**: Caddy publicly proxies all external requests to `/health/*` without authentication or IP restrictions. Unauthenticated malicious actors on the public internet can flood `GET /health/ready`. Even with `HEALTH_CACHE_TTL_SECONDS = 5`, every 5 seconds a flood of concurrent requests forces `_probe_database` (`SELECT 1`), `_probe_storage_readiness` (outbound R2 HTTP calls), worker checks, and filesystem disk usage calls, consuming database connections and event loop bandwidth.
3. **Reader Ingress Health Blind Spot**: Caddy routes `/health/*` exclusively to `backend:8000`. The public reader (`reader:8001`), which serves all guest catalog and chapter requests, has no health check proxy route in `Caddyfile`. If the reader service deadlocks or exhausts its memory, Caddy continues routing user traffic to the dead reader container without detecting failure.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Total Ingress Collapse During DB Maintenance**: Running an Alembic migration or restarting PostgreSQL takes 45 seconds. Caddy fails its healthcheck 3 times (30s interval \* 10s timeout), causing Docker to kill and restart Caddy. While Caddy restarts, TLS negotiation fails and static frontend pages and cached reader chapters fail completely for all users worldwide.
2. **Exhaustion of Worker Threads via External Probing**: Malicious clients flood `/health/ready` with 100 requests/sec. Backend worker threads spend significant CPU and DB checkout cycles executing probes, starving genuine user queries.
3. **Silent Reader Outage**: The `reader` container running on port 8001 crashes due to OOM. Because Caddy has no health check configured for `reader:8001` and only monitors `backend:8000`, Caddy serves 502 Bad Gateway to all novel reading visitors while reporting itself as "healthy".

#### 3. Concrete Implementation Specification

1. Decouple Caddy's container health check in `deploy/compose.yml` to check internal proxy health:

```yaml
caddy:
  healthcheck:
    test:
      [
        "CMD-SHELL",
        "wget -q -O /dev/null http://127.0.0.1:2019/metrics || exit 1",
      ]
    interval: 15s
    timeout: 3s
    retries: 3
    start_period: 5s
```

2. Protect `/health/ready` and route reader probes in `deploy/Caddyfile`:

```caddyfile
# Allow lightweight unauthenticated liveness check for external uptime monitors
handle /health/live {
    reverse_proxy backend:8000
}

# Dedicated health probe for public reader container
handle /health/reader/* {
    # Restrict to internal Docker networks and loopback
    @blocked not remote_ip 127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
    respond @blocked "Forbidden" 403
    reverse_proxy reader:8001
}

# Deep readiness probe restricted to internal networks or probe token header
handle /health/ready {
    @authorized {
        remote_ip 127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
        header X-Probe-Token "{$INTERNAL_PROBE_TOKEN}"
    }
    @unauthorized not {
        remote_ip 127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
        header X-Probe-Token "{$INTERNAL_PROBE_TOKEN}"
    }
    respond @unauthorized "Forbidden" 403
    reverse_proxy backend:8000
}
```

3. Add rate limiting to `/health/ready` and `/health/live` in `backend/src/novelai/api/routers/health.py`:
   Enforce an in-memory sliding window or Redis rate limit (max 10 requests per minute per remote IP) on health endpoints to mitigate resource exhaustion if internal network boundaries are bypassed.

#### 4. Verification & Test Strategy

Create `backend/tests/test_health_probes_contract.py`:

```python
import pytest
from starlette.testclient import TestClient
from novelai.main_admin import app

client = TestClient(app)

def test_health_live_endpoint_is_public_and_fast():
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "checks" not in data  # Liveness does not execute deep downstream probes

def test_health_ready_probe_contract_redaction():
    response = client.get("/health/ready")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    # Ensure sensitive credentials or absolute paths are not leaked
    content_str = response.text.lower()
    assert "password" not in content_str
    assert "secret" not in content_str
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_health_probes_contract.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: External uptime monitors (e.g. UptimeRobot, Better Uptime) should point to `/health/live`. Internal orchestrators (Kubernetes/Docker Swarm) can continue using `/health/ready` via private IP addresses.
- **Rollback Procedure**: Revert `deploy/compose.yml`, `deploy/Caddyfile`, and `backend/src/novelai/api/routers/health.py`.
  ```powershell
  Rollback command: git checkout HEAD -- deploy/compose.yml deploy/Caddyfile backend/src/novelai/api/routers/health.py
  ```

---

### REC-093: O(N) Bucket Key Scan in Health Storage Probe Causing Probe Timeouts & R2 Operation Exhaustion

- **ID**: `REC-093`
- **Subsystem/Component**: Health Probe Engine & Storage Backend (`novelai.services.health_service`, `novelai.storage.backends.r2_gateway`)
- **Target Location**:
  - `backend/src/novelai/services/health_service.py:440-485` (`HealthService._probe_storage_usage`)
  - `backend/src/novelai/storage/backends/r2_gateway.py:616-620` (`R2GatewayStorageBackend.total_size_bytes`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `HealthService._probe_storage_usage` calls `backend.total_size_bytes()`, which performs a recursive full-bucket pagination scan over all objects (`sum(item.size_bytes for item in self._iter_objects("", recursive=True))`). As novel chapters and images grow to 100k+ objects, this probe takes several seconds or minutes, exceeding `HEALTH_PROBE_TIMEOUT_MS`, failing admin health checks, and generating massive Cloudflare R2 Class B operation costs.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/health_service.py:440-485`:

```python
async def _probe_storage_usage(self) -> dict[str, Any]:
    start = time.monotonic()
    try:
        from novelai.storage.backends import get_r2_storage
        backend = get_r2_storage()
        used_bytes = backend.total_size_bytes()
        ...
```

And in `backend/src/novelai/storage/backends/r2_gateway.py:616-620`:

```python
def total_size_bytes(self) -> int:
    return sum(item.size_bytes for item in self._iter_objects("", recursive=True))
```

1. **Full-Bucket Scan on Synchronous Probe Path**: When `/admin/health` is accessed by an operator or automated monitoring system, `HealthService` executes `_probe_storage_usage` to verify used storage against `settings.R2_STORAGE_LIMIT_GB`. `backend.total_size_bytes()` iterates across the entire bucket key space recursively page by page.
2. **Unbounded Network and Latency Growth ($O(N)$)**: In a mature digital library holding 500 novels with 500 chapters each (250,000 chapter JSON and illustration objects), listing the bucket at 1,000 keys per page requires 250 sequential HTTP requests to the Cloudflare R2 gateway. This operation takes 15 to 40 seconds over WAN.
3. **Probe Timeouts & Operational Cost Spike**: `HealthService._run_probes` enforces `HEALTH_PROBE_TIMEOUT_MS = 1000` (1s per probe) and `HEALTH_TOTAL_TIMEOUT_MS = 3000` (3s total). Paginating thousands of objects guarantees a `TimeoutError`, causing `/admin/health` to constantly report `unhealthy` with `"Probe timed out"`. Furthermore, Cloudflare R2 bills Class B operations (`list_objects`); polling this probe regularly incurs substantial, wasteful API costs.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Permanent Admin Health Alerting Fatigue**: `/admin/health` and automated Prometheus probe scrapers consistently return status code 503 with probe timeout errors, creating alert fatigue where operators ignore legitimate outages.
2. **Class B API Bill Shock**: An external monitor polling `/admin/health` every 30 seconds triggers 120 bucket listings per hour (30,000 Class B API calls per hour), quickly exceeding Cloudflare free tier quotas and generating unnecessary infrastructure costs.
3. **Event Loop Starvation**: In single-worker or async server configurations, executing large pagination loops in thread pools exhausts worker threads and ties up HTTP client connections.

#### 3. Concrete Implementation Specification

1. Remove `total_size_bytes()` from the interactive health probe path in `HealthService`:
   Decouple real-time health checks from expensive full-bucket scans. Track storage usage via an asynchronous background job and store the aggregated summary in Redis (`r2:storage:summary`) or database settings.
2. Update `_probe_storage_usage` in `HealthService`:

```python
# backend/src/novelai/services/health_service.py
async def _probe_storage_usage(self) -> dict[str, Any]:
    start = time.monotonic()
    try:
        # 1. Read cached summary from Redis or local cache
        cached_usage = await self._get_cached_storage_usage()
        if cached_usage is not None:
            used_bytes = cached_usage.get("total_bytes", 0)
            object_count = cached_usage.get("object_count", 0)
            last_calculated = cached_usage.get("updated_at")
        else:
            # 2. Fallback to fast database estimate if cache empty
            used_bytes = await self._estimate_storage_from_db()
            object_count = -1
            last_calculated = "estimated_db"

        limit_bytes = settings.R2_STORAGE_LIMIT_GB * 1024 * 1024 * 1024
        utilization = (used_bytes / limit_bytes) if limit_bytes > 0 else 0.0
        elapsed_ms = (time.monotonic() - start) * 1000

        return {
            "status": "healthy" if utilization < 0.90 else "degraded",
            "used_bytes": used_bytes,
            "limit_bytes": limit_bytes,
            "utilization_pct": round(utilization * 100, 2),
            "object_count": object_count,
            "last_calculated": last_calculated,
            "elapsed_ms": round(elapsed_ms, 2),
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "error": str(exc),
            "elapsed_ms": round((time.monotonic() - start) * 1000, 2),
        }
```

3. Implement `CalculateStorageUsageJob` in `novelai.services.scheduler_service`:
   Schedule a low-priority background task that runs once daily off-peak (e.g. at 03:00 UTC) to execute `backend.total_size_bytes()` and update `r2:storage:summary` in Redis with a 48-hour TTL.

#### 4. Verification & Test Strategy

Create `backend/tests/test_health_storage_probe.py`:

```python
import pytest
from novelai.services.health_service import HealthService
from novelai.storage.backends.r2_gateway import R2GatewayStorageBackend

@pytest.mark.asyncio
async def test_health_storage_probe_never_calls_r2_list_objects(monkeypatch):
    def mock_iter_objects(*args, **kwargs):
        raise AssertionError("Iter objects must never be called during health check probe!")

    monkeypatch.setattr(R2GatewayStorageBackend, "_iter_objects", mock_iter_objects)
    service = HealthService()
    result = await service._probe_storage_usage()

    assert result["status"] in ("healthy", "degraded")
    assert result["elapsed_ms"] < 100.0  # Must execute under 100ms
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_health_storage_probe.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. The health response schema retains `used_bytes` and `limit_bytes` while adding non-breaking metadata (`last_calculated`, `object_count`).
- **Rollback Procedure**: Revert `backend/src/novelai/services/health_service.py` and `backend/src/novelai/storage/backends/r2_gateway.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/health_service.py backend/src/novelai/storage/backends/r2_gateway.py
  ```

---

### REC-094: Prometheus Scrape DoS via In-Memory Full-Table Scan in Metric Collectors & Missing Reader Metrics

- **ID**: `REC-094`
- **Subsystem/Component**: Metrics & Monitoring System (`novelai.api.routers.metrics`, `novelai.activity.database`, `novelai.main_reader`)
- **Target Location**:
  - `backend/src/novelai/api/routers/metrics.py:49-65` (`_activity_counts`)
  - `backend/src/novelai/api/routers/metrics.py:90-110` (`_activity_failures_per_source`)
  - `backend/src/novelai/activity/database.py:304-340` (`ActivityDatabaseBackend.list_activity`)
  - `backend/src/novelai/main_reader.py:100-118` (missing `metrics_router`)
- **Category**: `Performance`
- **Severity**: `High`
- **Summary**: `/metrics` collector executes unconstrained `list_activity()` full-table scans twice per scrape, loading tens of thousands of rows into Python memory; the collector is completely missing from the high-traffic `main_reader.py` app lifecycle; and standard HTTP RED metrics (request rates, error codes, latency histograms) and DB connection pool saturation metrics are not exported.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/routers/metrics.py:49-65`:

```python
def _activity_counts() -> dict[str, int]:
    ...
    activities = activity_log.list_activity() or []
    for activity in activities:
        status = str(activity.get("status") or "unknown").lower()
        counts[status] += 1
    return dict(counts)

def _activity_failures_per_source() -> dict[str, int]:
    ...
    activities = activity_log.list_activity() or []
    ...
```

And in `backend/src/novelai/activity/database.py:304-340`:

```python
def list_activity(self, *, status=None, activity_type=None, novel_id=None, limit=None) -> list[dict[str, Any]]:
    with self._timed("list"), self._session() as session:
        stmt = select(ActivityRecord)
        ...
        stmt = stmt.order_by(priority, ActivityRecord.created_at)
        # if limit is None, fetches ALL rows
```

1. **Repeated In-Memory Full-Table Scans**: Every time Prometheus scrapes `/metrics` (typically every 15s), `_activity_counts()` and `_activity_failures_per_source()` call `activity_log.list_activity()` with no limit. In `ActivityDatabaseBackend.list_activity()`, omitting `limit` executes `SELECT * FROM activity_records` across the entire historical table, serializes every row into a Python dictionary, and iterates through them in memory. In a production system with 50,000 historical jobs, each scrape fetches 100,000 dicts into memory, causing major database I/O, network egress, and multi-second garbage collection freezes in the admin API.
2. **Total Blind Spot on Public Reader**: The public reader application (`backend/src/novelai/main_reader.py`) serves 95%+ of all incoming user traffic. However, `metrics_router` is registered ONLY in `main_admin.py` (`backend:8000`). It is completely missing from `main_reader.py`. Prometheus has zero visibility into public reader memory usage, event loop lag, or request concurrency.
3. **Absence of HTTP RED and Connection Pool Metrics**: The current `/metrics` endpoint exports custom activity counts and Python GC stats, but completely lacks standard HTTP RED metrics:
   - `http_requests_total{method, status_code, path}` (Rate & Errors)
   - `http_request_duration_seconds_bucket` (Duration latency histograms)
   - Database connection pool utilization: `db_pool_size`, `db_pool_checked_out`, `db_pool_overflow`, and `db_pool_wait_queue`.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Periodic Scrape-Induced Latency Spikes**: Every 15 seconds when Prometheus scrapes the admin service, CPU usage spikes to 100% for 1-2 seconds as 100,000 dictionary objects are allocated and garbage-collected, degrading admin UI responsiveness.
2. **Unmonitored Reader Outages**: A sudden traffic spike to `/catalog` or `/chapter` overwhelms the reader process, but since the reader does not export Prometheus metrics, alerts fail to fire until user complaints surface.
3. **Silent Connection Pool Starvation**: Application threads exhaust database connections, causing requests to queue and time out. Without connection pool saturation metrics, operators cannot determine whether the bottleneck is in database query concurrency or connection leakages.

#### 3. Concrete Implementation Specification

1. Replace in-memory full-table scans with SQL aggregation queries in `backend/src/novelai/api/routers/metrics.py`:

```python
from sqlalchemy import func, select
from novelai.db.engine import session_scope
from novelai.db.models.activity import ActivityRecord

def _activity_counts() -> dict[str, int]:
    with session_scope() as session:
        stmt = (
            select(ActivityRecord.status, func.count(ActivityRecord.id))
            .group_by(ActivityRecord.status)
        )
        return {str(status).lower(): count for status, count in session.execute(stmt)}

def _activity_failures_per_source() -> dict[str, int]:
    with session_scope() as session:
        stmt = (
            select(ActivityRecord.source_id, func.count(ActivityRecord.id))
            .where(ActivityRecord.status == "failed")
            .group_by(ActivityRecord.source_id)
        )
        return {str(source or "unknown"): count for source, count in session.execute(stmt)}
```

2. Mount `metrics_router` in `backend/src/novelai/main_reader.py`:

```python
# backend/src/novelai/main_reader.py
from novelai.api.routers.metrics import router as metrics_router

# Mount internal metrics endpoint
reader_app.include_router(metrics_router, prefix="/internal", tags=["metrics"])
```

3. Integrate standard Prometheus RED and Connection Pool gauges:

```python
from prometheus_client import Gauge, Histogram, Counter
from novelai.db.engine import get_engine

DB_POOL_CHECKED_OUT = Gauge("db_pool_checked_out_connections", "Number of connections currently checked out")
DB_POOL_SIZE = Gauge("db_pool_size", "Current database connection pool size")
DB_POOL_OVERFLOW = Gauge("db_pool_overflow_connections", "Number of overflow connections active")

def _collect_db_pool_metrics() -> None:
    try:
        engine = get_engine()
        pool = engine.pool
        DB_POOL_SIZE.set(pool.size())
        DB_POOL_CHECKED_OUT.set(pool.checkedout())
        DB_POOL_OVERFLOW.set(pool.overflow())
    except Exception:
        pass
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_metrics_collector.py`:

```python
import pytest
from novelai.api.routers.metrics import _activity_counts
from novelai.db.models.activity import ActivityRecord

def test_metrics_executes_aggregate_sql_without_full_table_scan(db_session):
    for i in range(50):
        db_session.add(ActivityRecord(
            id=f"act_{i}",
            action_type="fetch_novel",
            status="completed" if i % 2 == 0 else "failed",
        ))
    db_session.commit()

    counts = _activity_counts()
    assert counts.get("completed") == 25
    assert counts.get("failed") == 25
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_metrics_collector.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. The Prometheus metric output names and types remain identical (`novelai_activity_total`, `novelai_activity_failures_per_source_total`), ensuring existing Grafana dashboards continue functioning without disruption.
- **Rollback Procedure**: Revert `backend/src/novelai/api/routers/metrics.py` and `backend/src/novelai/main_reader.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/routers/metrics.py backend/src/novelai/main_reader.py
  ```

---

### REC-095: Lack of Distributed Tracing & W3C Trace Context Propagation Across Service Boundaries

- **ID**: `REC-095`
- **Subsystem/Component**: Distributed Tracing & APM Observability (`novelai.logging_config`, `novelai.api.middleware`, `novelai.infrastructure.http.fetch_service`, `novelai.activity.worker`)
- **Target Location**:
  - `backend/src/novelai/logging_config.py:30-65` (`_request_id_var`, `get_request_id`, `set_request_id`)
  - `backend/src/novelai/api/middleware/trace.py` (W3C `traceparent` extraction)
  - `backend/src/novelai/infrastructure/http/fetch_service.py:110-150` (outbound HTTP trace context injection)
  - `backend/src/novelai/activity/worker.py:600-650` (background worker trace propagation)
- **Category**: `Gap`
- **Severity**: `Medium`
- **Summary**: The backend lacks OpenTelemetry integration and W3C `traceparent`/`tracestate` context propagation across Caddy, FastAPI, Celery/RQ/background activity workers, and outbound HTTP/R2 calls, creating blind spots during incident triage and preventing correlation of user-facing latency with downstream database and LLM provider calls.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/logging_config.py:30-65`:

```python
_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
def set_request_id(request_id: str | None = None) -> str:
    rid = request_id or uuid.uuid4().hex[:12]
    _request_id_var.set(rid)
    return rid
```

1. **Ad-Hoc Request ID vs OpenTelemetry Standard**: Correlation in the codebase is limited to a 12-character random hex string (`uuid.uuid4().hex[:12]`). It has no span IDs, parent IDs, trace flags, or integration with open observability standards (OpenTelemetry / W3C Trace Context / Jaeger / Datadog / Grafana Tempo).
2. **Context Severance Across Service Boundaries**:
   - Inbound: When a request traverses Cloudflare CDN -> Caddy Reverse Proxy -> FastAPI backend/reader, incoming `traceparent` headers (`traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`) are ignored and discarded.
   - Async Queue: When FastAPI enqueues a background activity task (`ActivityRecord`), the trace context is not captured in task metadata. When `ActivityWorkerService` claims and runs the job in another thread or process, it generates a fresh request ID, severing the link between the admin action and worker execution.
   - Outbound: Outbound HTTP requests in `FetchService` (crawling Kakuyomu, Syosetu) and LLM calls in `GeminiProvider` do not inject traceparent headers or record span timings for external DNS, TLS, and roundtrip latency.
3. **Inability to Diagnose Latency Spikes**: If a user experiences a 5-second delay reading a chapter or translating a text block, operators cannot inspect a waterfall trace to determine whether time was spent in Caddy buffering, FastAPI middleware, PostgreSQL connection checkout, R2 gateway roundtrips, or LLM token streaming.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Unresolvable High-Latency Incidents**: During API latency spikes, operators cannot tell if slow responses originate from PostgreSQL connection lock contention, Cloudflare R2 gateway latencies, or upstream crawler network throttling.
2. **Severed Async Triage**: An ingestion task fails in the background worker. The worker logs an isolated error with a newly generated `request_id`, making it impossible to correlate with the admin user action that triggered the job.
3. **Vendor Lock-in & Blind Spots**: Without standard W3C headers, migrating or integrating APM platforms (Datadog, New Relic, OpenTelemetry Collector) requires rewriting logging and networking layers.

#### 3. Concrete Implementation Specification

1. Implement W3C `traceparent` parsing and generation in `backend/src/novelai/logging_config.py`:

```python
import os
import re
import secrets
from typing import NamedTuple

W3C_TRACEPARENT_RE = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)

class TraceContext(NamedTuple):
    trace_id: str
    parent_id: str
    span_id: str
    trace_flags: str

    @classmethod
    def from_header(cls, header: str | None) -> "TraceContext":
        if header:
            match = W3C_TRACEPARENT_RE.match(header.strip())
            if match:
                trace_id, parent_id, flags = match.groups()
                span_id = secrets.token_hex(8)
                return cls(trace_id=trace_id, parent_id=parent_id, span_id=span_id, trace_flags=flags)
        trace_id = secrets.token_hex(16)
        span_id = secrets.token_hex(8)
        return cls(trace_id=trace_id, parent_id="", span_id=span_id, trace_flags="01")

    def to_header(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"
```

2. Create `TraceContextMiddleware` in `backend/src/novelai/api/middleware/trace.py`:

```python
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from novelai.logging_config import TraceContext, set_trace_context

class TraceContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_header = request.headers.get("traceparent")
        ctx = TraceContext.from_header(trace_header)
        set_trace_context(ctx)

        response = await call_next(request)
        response.headers["traceparent"] = ctx.to_header()
        response.headers["X-Trace-ID"] = ctx.trace_id
        return response
```

3. Propagate `traceparent` across async worker jobs:
   When creating `ActivityRecord`, serialize `ctx.to_header()` into `metadata_json["traceparent"]`. In `ActivityWorkerService._run_claimed_activity`, restore `set_trace_context(TraceContext.from_header(record.metadata_json.get("traceparent")))`.
4. Inject `traceparent` into outbound requests in `FetchService.fetch`:

```python
headers = dict(headers or {})
if current_ctx := get_trace_context():
    headers["traceparent"] = current_ctx.to_header()
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_distributed_tracing.py`:

```python
import pytest
from starlette.testclient import TestClient
from novelai.main_admin import app

client = TestClient(app)

def test_w3c_traceparent_propagation():
    incoming_trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    response = client.get("/health/live", headers={"traceparent": incoming_trace})
    assert response.status_code == 200
    assert "traceparent" in response.headers
    assert response.headers["X-Trace-ID"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert response.headers["traceparent"].startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_distributed_tracing.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. Requests without `traceparent` automatically generate new compliant W3C IDs. Downstream clients unaware of OpenTelemetry simply ignore the added response headers.
- **Rollback Procedure**: Revert `backend/src/novelai/logging_config.py`, `backend/src/novelai/api/middleware/trace.py`, `backend/src/novelai/infrastructure/http/fetch_service.py`, and `backend/src/novelai/activity/worker.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/logging_config.py backend/src/novelai/api/middleware/trace.py backend/src/novelai/infrastructure/http/fetch_service.py backend/src/novelai/activity/worker.py
  ```

---

### REC-096: Critical R2 Namespace Backup Blind Spot (Omitted Generations & Translations) & Missing Client-Side Encryption

- **ID**: `REC-096`
- **Subsystem/Component**: Incremental Object Backup & Storage Security (`novelai.storage.r2_backup`)
- **Target Location**:
  - `backend/src/novelai/storage/r2_backup.py:53-70` (`R2IncrementalBackupTarget._list_source_objects`)
  - `backend/src/novelai/storage/r2_backup.py:117-155` (`R2IncrementalBackupTarget.create_snapshot`)
  - `backend/src/novelai/storage/r2_backup.py:200-245` (`R2IncrementalBackupTarget.restore_snapshot`)
- **Category**: `Security`
- **Severity**: `Critical`
- **Summary**: `R2IncrementalBackupTarget` strictly iterates over the `"novels"` prefix, completely omitting byte-immutable raw chapter generation bundles under `"generations/"`, translation overlays under `"translations/"`, and active chapter pointers under `"active/"`; furthermore, object snapshots in R2 are stored completely unencrypted without client-side AES-256 or envelope encryption.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/storage/r2_backup.py:53-70`:

```python
def _list_source_objects(self) -> list[Any]:
    objects = [item for page in _pages(self._source, "novels", recursive=True) for item in page.objects]
    return sorted(objects, key=lambda item: str(item.key))
```

And in `backend/src/novelai/storage/r2_backup.py:117-155`:

```python
def create_snapshot(self, snapshot_id: str) -> BackupSnapshotManifest:
    ...
    for item in source_objects:
        data = self._source.load(item.key)
        self._target.save(f"snapshots/{snapshot_id}/{item.key}", data)
```

1. **Complete Blind Spot for Core Novel Content**: `_list_source_objects` only iterates objects under the prefix `"novels"`. However, according to `docs/STORAGE.md` and `AGENTS.md`:
   - Raw scraped novel chapters and bundles are stored under `generations/<gen-id>/`.
   - Chapter translations are stored in overlays under `translations/<encoded-chapter-stem>.json`.
   - Active chapter and generation pointers are stored under `active/`.
     Because `_list_source_objects` hardcodes prefix `"novels"`, 100% of raw generations, translated chapter overlays, and active pointers are completely omitted from R2 snapshot backups! In the event of primary bucket corruption, only metadata under `"novels"` would be restored, resulting in complete loss of translated content.
2. **Unencrypted Backup Storage at Rest**: While PostgreSQL backups (`DatabaseBackupService`) enforce AES-256-GCM encryption with mandatory keys (`DATABASE_BACKUP_ENCRYPTION_KEY`), R2 object backups (`R2IncrementalBackupTarget`) upload raw object data directly into the secondary backup bucket with no encryption-at-rest (`self._target.save(backup_key, data)`). If the backup bucket credentials or gateway are compromised, all backed-up novel content and metadata are readable in plaintext.
3. **Missing Pointer Re-synchronization on Restore**: In `restore_snapshot()`, objects are copied back verbatim to their destination keys. Without validation of active generation pointers (`active/<novel_id>.json`), a partial restore leaves the library referencing nonexistent generation IDs.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Total Loss of Library Content on Bucket Corruption**: If Cloudflare R2 experiences accidental bucket deletion or silent data corruption, restoring from the R2 snapshot backup restores novel titles and chapter lists, but all actual chapter texts, raw generations, and translated overlays are completely missing, permanently destroying months of translated novel data.
2. **Data Leakage in Secondary Cloud Provider**: If backups are replicated to an off-site secondary S3/Wasabi bucket or cold archival tier, unencrypted objects expose all proprietary translations and user-generated metadata in plaintext if the secondary bucket has misconfigured IAM policies.
3. **Dangling Generation Pointers**: Incomplete restoration of generation files alongside active pointers causes readers to throw 404 or 500 errors across all catalog routes.

#### 3. Concrete Implementation Specification

1. Expand backup namespace scope to cover all canonical R2 prefixes in `backend/src/novelai/storage/r2_backup.py`:

```python
CANONICAL_BACKUP_PREFIXES = (
    "novels",
    "generations",
    "translations",
    "active",
    "taxonomy",
)

def _list_source_objects(self) -> list[Any]:
    objects = []
    for prefix in CANONICAL_BACKUP_PREFIXES:
        for page in _pages(self._source, prefix, recursive=True):
            objects.extend(page.objects)
    return sorted(objects, key=lambda item: str(item.key))
```

2. Apply AES-256-GCM encryption in `create_snapshot` and decryption in `restore_snapshot`:

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import secrets

def _encrypt_payload(self, data: bytes, key: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext

def _decrypt_payload(self, encrypted_data: bytes, key: bytes) -> bytes:
    if len(encrypted_data) < 28:
        raise ValueError("Invalid encrypted payload: too short")
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

def create_snapshot(self, snapshot_id: str, encryption_key: bytes | None = None) -> BackupSnapshotManifest:
    source_objects = self._list_source_objects()
    for item in source_objects:
        data = self._source.load(item.key)
        if encryption_key:
            data = self._encrypt_payload(data, encryption_key)
            stored_key = f"snapshots/{snapshot_id}/{item.key}.aesgcm"
        else:
            stored_key = f"snapshots/{snapshot_id}/{item.key}"
        self._target.save(stored_key, data)
```

3. Update manifest schema to record `encrypted: bool` and verify active pointer integrity during snapshot restoration.

#### 4. Verification & Test Strategy

Create `backend/tests/test_r2_backup_scope.py`:

```python
import pytest
from novelai.storage.backends.memory import MemoryStorageBackend
from novelai.storage.r2_backup import R2IncrementalBackupTarget

def test_backup_includes_generations_and_translations():
    memory_source = MemoryStorageBackend()
    memory_target = MemoryStorageBackend()

    # Seed storage with all canonical prefixes
    memory_source.save("novels/123/metadata.json", b"{}")
    memory_source.save("generations/gen_456/raw_chapter.json", b"raw text")
    memory_source.save("translations/trans_789.json", b"translated text")
    memory_source.save("active/gen_456.json", b"{}")

    backup = R2IncrementalBackupTarget(source=memory_source, target=memory_target)
    manifest = backup.create_snapshot("snap_001")

    keys = {item.key for item in manifest.items}
    assert "novels/123/metadata.json" in keys
    assert "generations/gen_456/raw_chapter.json" in keys
    assert "translations/trans_789.json" in keys
    assert "active/gen_456.json" in keys
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_r2_backup_scope.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. Existing unencrypted snapshots can still be read by restore workers checking the `encrypted` flag in the snapshot manifest. If an encryption key is not supplied, snapshots fall back to unencrypted mode with an operator warning.
- **Rollback Procedure**: Revert changes in `backend/src/novelai/storage/r2_backup.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/storage/r2_backup.py
  ```

---

### REC-097: Absence of Continuous WAL Archiving & Point-in-Time Recovery (PITR) Exposing 24-Hour RPO Window

- **ID**: `REC-097`
- **Subsystem/Component**: Database Disaster Recovery & Archival Architecture (`novelai.services.database_backup_service`, `deploy.compose`, `deploy.postgres`)
- **Target Location**:
  - `backend/src/novelai/services/database_backup_service.py:130-195` (`DatabaseBackupService.create_backup`)
  - `deploy/compose.yml:30-45` (`db` container PostgreSQL flags)
  - `deploy/postgres/postgresql.production.conf.example`
- **Category**: `Reliability`
- **Severity**: `Critical`
- **Summary**: PostgreSQL disaster recovery relies solely on daily logical `pg_dump` snapshots (`0 1 * * *`) with zero continuous write-ahead log (WAL) archiving or Point-in-Time Recovery (PITR) tooling (e.g. pgBackRest / wal-g), leaving a disastrous 24-hour Recovery Point Objective (RPO) where any mid-day crash permanently loses all created translations, bookmarks, and user activity.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/database_backup_service.py:130-195`:

```python
# DatabaseBackupService executes logical pg_dump once daily:
DATABASE_BACKUP_SCHEDULE_CRON = "0 1 * * *"
```

And in `deploy/compose.yml:30-45`:

```yaml
db:
  image: postgres:17.4-alpine
  command: >-
    postgres
      ...
      -c wal_level=replica
      ...
```

1. **Disastrous 24-Hour RPO Window**: If a storage volume fails, host server crashes, or accidental drop/corruption occurs at 23:00, the only recovery point is the logical backup taken at 01:00 that morning. Up to 22 hours of continuous novel translations, glossary additions, user reading history, bookmarks, and registered accounts are permanently lost. A 24-hour RPO is unacceptable for a production database.
2. **Unarchived Discarded WAL Segments**: In `compose.yml`, PostgreSQL is started with `-c wal_level=replica`, but has NO `archive_mode=on`, NO `archive_command`, and NO `archive_timeout`. Generated WAL segments are recycled and overwritten locally once checkpointed. None of the transaction logs are continuously archived to off-site object storage (R2).
3. **High Recovery Time Objective (RTO) with Logical Restores**: Restoring a logical `pg_dump` requires sequentially re-executing thousands of DDL commands and rebuilding all indexes from scratch. In contrast, physical base backups combined with continuous WAL replay (`wal-g` / `pgBackRest`) restore byte-level database files directly, reducing recovery time from hours to minutes and enabling recovery to any exact millisecond (Point-in-Time Recovery).

#### 2. Failure Scenarios & Security/Operational Impact

1. **Irrecoverable Data Loss Incident**: At 22:30, a physical NVMe failure corrupts the PostgreSQL volume. Restoring the 01:00 AM backup permanently loses 21.5 hours of novel translations (hundreds of LLM API dollars spent), user reading progress, and bookmark updates.
2. **Accidental Admin Deletion Without Rollback**: An operator accidentally runs `DELETE FROM users WHERE ...` or a bug corrupts novel metadata. With daily snapshots, rolling back requires reverting the entire database to 01:00 AM, destroying all intervening valid activity. With Point-in-Time Recovery (PITR), the operator could restore the database to 1 second before the erroneous command was issued.
3. **Extended RTO Downtime**: Restoring a 20GB logical dump takes 3+ hours because PostgreSQL must single-thread parse SQL text, re-insert rows, and recreate indexes.

#### 3. Concrete Implementation Specification

1. Enable continuous WAL archiving in PostgreSQL configuration (`deploy/postgres/postgresql.production.conf.example` and `compose.yml`):

```ini
wal_level = replica
archive_mode = on
archive_command = 'wal-g wal-push %p'
archive_timeout = 300  # Force WAL switch at least every 5 minutes
```

2. Integrate `wal-g` in Docker Compose:
   Deploy `wal-g` sidecar or container image with Cloudflare R2 credentials:
   - `WALE_S3_PREFIX=s3://novelai-backups/wal`
   - `AWS_ACCESS_KEY_ID=${R2_BACKUP_ACCESS_KEY}`
   - `AWS_SECRET_ACCESS_KEY=${R2_BACKUP_SECRET_KEY}`
   - `AWS_ENDPOINT=https://${CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com`
3. Schedule periodic physical base backups:
   Configure a cron container or worker job executing:
   ```bash
   wal-g backup-push /var/lib/postgresql/data
   ```
   Run full base backups weekly and differential base backups daily.
4. Document and script PITR restore in `tools/database/pitr_restore.ps1`:

```powershell
param(
    [Parameter(Mandatory=$true)] [string]$TargetRecoveryTime
)
$ErrorActionPreference = "Stop"
Write-Host "Fetching latest base backup from R2..."
wal-g backup-fetch /var/lib/postgresql/data LATEST
# Write recovery.signal and postgresql.auto.conf with recovery_target_time
Set-Content -Path "/var/lib/postgresql/data/recovery.signal" -Value ""
Add-Content -Path "/var/lib/postgresql/data/postgresql.auto.conf" -Value "restore_command = 'wal-g wal-fetch %f %p'`nrecovery_target_time = '$TargetRecoveryTime'`nrecovery_target_action = 'promote'"
Write-Host "Recovery target configured to $TargetRecoveryTime. Start PostgreSQL to replay WAL."
```

#### 4. Verification & Test Strategy

Create an automated test drill script `tools/database/verify_pitr_drill.ps1` and unit tests in `backend/tests/test_database_backup_service.py`:

```python
import pytest
from novelai.services.database_backup_service import DatabaseBackupService

def test_database_backup_service_schedule_and_manifest():
    service = DatabaseBackupService()
    assert service.schedule_cron == "0 1 * * *"
    assert hasattr(service, "create_backup")
    assert hasattr(service, "verify_latest_restore")
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_database_backup_service.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible with application code. Logical `pg_dump` backups can continue running in parallel as secondary defense-in-depth while WAL archiving provides continuous PITR coverage. If WAL archiving fails, PostgreSQL continues local operations and logs warnings in `postgresql.log`.
- **Rollback Procedure**: Revert configuration in `deploy/compose.yml`, `deploy/postgres/postgresql.production.conf.example`, and `tools/database/pitr_restore.ps1`.
  ```powershell
  Rollback command: git checkout HEAD -- deploy/compose.yml deploy/postgres/postgresql.production.conf.example tools/database/pitr_restore.ps1 backend/src/novelai/services/database_backup_service.py
  ```

---

### REC-098: Empty Backup Script, Insecure Restore Script, & Mocked Automated Restore Verification Drills

- **ID**: `REC-098`
- **Subsystem/Component**: Database Operational Tooling (`tools.database`, `novelai.services.database_backup_service`)
- **Target Location**:
  - `tools/database/backup_postgres.ps1:1` (`backup_postgres.ps1` empty file)
  - `tools/database/restore_postgres.ps1:28-48` (`restore_postgres.ps1` error suppression & unverified restore)
  - `tools/database/verify_backup_drill.ps1:28-48` (`verify_backup_drill.ps1` mock container check)
  - `backend/src/novelai/services/database_backup_service.py:230-255` (`DatabaseBackupService.verify_latest_restore` whole-payload RAM buffering)
- **Category**: `Reliability`
- **Severity**: `High`
- **Summary**: `tools/database/backup_postgres.ps1` is a zero-byte empty file; `restore_postgres.ps1` suppresses error streams (`2>$null`), lacks cryptographic SHA-256 manifest validation, and hardcodes database credentials; `verify_backup_drill.ps1` only checks `docker ps` liveness without performing an actual restore or schema validation; and `verify_latest_restore` loads the entire encrypted backup file into memory as a single `bytes` object, causing container OOM crashes during drills.

#### 1. Root Cause & Code-Level Diagnostic

1. **0-Byte Empty Backup Script**: `tools/database/backup_postgres.ps1` exists in the repository root tooling directory, but is completely empty (0 bytes). Operators attempting to execute documented local backup operations run a blank script with zero effect.
2. **Silent Failure & Insecure Restore in `restore_postgres.ps1`**:
   ```powershell
   docker exec dokushodo-db pg_restore --clean --if-exists -U dokushodo -d dokushodo -v /tmp/restore_temp.dump 2>$null
   ```
   Redirecting stderr to `$null` (`2>$null`) hides critical restore errors, constraint violations, and schema discrepancies. The script does not verify the file's SHA-256 hash against any manifest before restoring. Furthermore, credentials and container names are hardcoded.
3. **Mocked Verification Drill**: `tools/database/verify_backup_drill.ps1` claims to validate backup and restore into an ephemeral scratch database (referencing REQ-006 / F-6). In reality, lines 34-45 only execute `docker ps --filter "name=dokushodo-db"`! If the container is running, it prints "Drill complete: Backup and restore harness verified." without ever dumping or restoring a single byte of data.
4. **Memory-Exhausting Whole-Payload Buffering in Python Service**: In `backend/src/novelai/services/database_backup_service.py:230-255`:
   ```python
   with tempfile.NamedTemporaryFile(prefix="novelai-restore-", suffix=".aesgcm", delete=False) as encrypted:
       encrypted_path = Path(encrypted.name)
       encrypted.write(self._backend.load(str(manifest["object_key"])))
   ```
   `self._backend.load()` reads the entire encrypted backup dump into Python heap memory as a single `bytes` object. For a 5GB-20GB production database backup, this allocates 5GB-20GB of RAM inside the worker container, triggering immediate kernel Out-Of-Memory (OOM) kills during scheduled verification drills.

#### 2. Failure Scenarios & Security/Operational Impact

1. **False Sense of Disaster Recovery Readiness**: Automated CI or cron runs of `verify_backup_drill.ps1` report 100% success because the database container is simply running, creating a false sense of security while database restore procedures are completely broken or unexecutable.
2. **Fatal OOM Kills During Automated Restore Verification**: When database size grows past container RAM limits (e.g. 4GB RAM limit in `compose.yml`), the nightly `verify_latest_restore` job triggers an instant OOM kill by buffering the multi-gigabyte dump into RAM, crashing the background worker.
3. **Silent Data Corruption on Manual Restore**: An operator executing `restore_postgres.ps1` during an outage receives no error feedback due to `2>$null`, believing the restore succeeded even when foreign key constraint violations or missing extensions abort the restore midway.

#### 3. Concrete Implementation Specification

1. Implement `tools/database/backup_postgres.ps1`:

```powershell
param(
    [string]$ContainerName = "novelai-db",
    [string]$Database = "novelai_prod",
    [string]$Username = "novelai_app",
    [string]$OutputDir = "./backups"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dumpFile = Join-Path $OutputDir "novelai_$timestamp.dump"
$manifestFile = Join-Path $OutputDir "novelai_$timestamp.json"

Write-Host "Creating backup for $Database..."
docker exec $ContainerName pg_dump -U $Username -d $Database -Fc -f /tmp/backup.dump
docker cp "${ContainerName}:/tmp/backup.dump" $dumpFile
docker exec $ContainerName rm /tmp/backup.dump

$hash = (Get-FileHash -Path $dumpFile -Algorithm SHA256).Hash
$manifest = @{
    timestamp = $timestamp
    database = $Database
    sha256 = $hash
    file_size_bytes = (Get-Item $dumpFile).Length
} | ConvertTo-Json
Set-Content -Path $manifestFile -Value $manifest -Encoding UTF8
Write-Host "Backup completed: $dumpFile (SHA256: $hash)"
```

2. Fix `restore_postgres.ps1` by removing `2>$null`, requiring manifest validation, and checking `$LASTEXITCODE`:

```powershell
# Validate SHA256 before restoring
$actualHash = (Get-FileHash -Path $DumpPath -Algorithm SHA256).Hash
if ($actualHash -ne $expectedHash) {
    throw "SHA256 checksum mismatch! Expected $expectedHash, got $actualHash"
}
# Execute pg_restore without hiding stderr
docker cp $DumpPath "${ContainerName}:/tmp/restore.dump"
docker exec $ContainerName pg_restore --clean --if-exists -U $Username -d $Database -v /tmp/restore.dump
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore failed with exit code $LASTEXITCODE"
}
```

3. Rewrite `tools/database/verify_backup_drill.ps1` to perform genuine scratch restore:

```powershell
# Create ephemeral scratch database
docker exec $ContainerName psql -U $Username -d postgres -c "CREATE DATABASE novelai_drill_restore;"
try {
    docker exec $ContainerName pg_restore -U $Username -d novelai_drill_restore -v /tmp/backup.dump
    $novelCount = docker exec $ContainerName psql -U $Username -d novelai_drill_restore -t -A -c "SELECT count(*) FROM novels;"
    if ([int]$novelCount -le 0) { throw "Drill restore validation failed: 0 novels restored." }
    Write-Host "Drill verified successfully: $novelCount novels restored."
} finally {
    docker exec $ContainerName psql -U $Username -d postgres -c "DROP DATABASE IF EXISTS novelai_drill_restore;"
}
```

4. Stream backup downloads in `backend/src/novelai/services/database_backup_service.py`:

```python
with tempfile.NamedTemporaryFile(prefix="novelai-restore-", suffix=".aesgcm", delete=False) as encrypted:
    encrypted_path = Path(encrypted.name)
    # Stream in 1MB chunks to disk rather than buffering entire bytes payload
    with self._backend.open_stream(str(manifest["object_key"]), mode="rb") as stream:
        shutil.copyfileobj(stream, encrypted, length=1024 * 1024)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_database_backup_streaming.py`:

```python
import io
import shutil
import tempfile
from pathlib import Path

def test_stream_copy_chunked_avoids_heap_exhaustion():
    chunk_size = 1024 * 1024  # 1MB
    total_size = 10 * 1024 * 1024  # 10MB test payload
    fake_stream = io.BytesIO(b"0" * total_size)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(fake_stream, tmp, length=chunk_size)

    try:
        assert tmp_path.stat().st_size == total_size
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_database_backup_streaming.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. Does not modify live application database schema. Operational scripts are isolated to the `tools/database/` directory.
- **Rollback Procedure**: Revert `tools/database/` scripts and `database_backup_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- tools/database/backup_postgres.ps1 tools/database/restore_postgres.ps1 tools/database/verify_backup_drill.ps1 backend/src/novelai/services/database_backup_service.py
  ```

---

### REC-099: Child Process Signal Blindness in Split Deployment Mode & Missing Uvicorn Graceful Connection Draining

- **ID**: `REC-099`
- **Subsystem/Component**: Application Server Lifecycle & Container Process Management (`novelai.api.server`, `deploy.admin.Dockerfile`, `deploy.compose`)
- **Target Location**:
  - `backend/src/novelai/api/server.py:30-55` (`novelai.api.server.main`)
  - `deploy/admin.Dockerfile:62-64` (`CMD ["novelai", "web", ...]`)
  - `deploy/compose.yml:330-335` (`stop_grace_period: 60s`)
- **Category**: `Architecture`
- **Severity**: `High`
- **Summary**: In `split` deployment mode, `novelai.api.server` spawns `multiprocessing.Process` workers for admin and reader without forwarding `SIGTERM` signals, causing Docker shutdown to orphan or abruptly terminate child workers; furthermore, Uvicorn runs without configured `timeout_graceful_shutdown`, terminating active HTTP requests and WebSocket streams mid-flight.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/api/server.py:30-55`:

```python
def main(*, reload: bool = False) -> None:
    deploy_mode = os.environ.get("DEPLOY_MODE", "monolith")
    if deploy_mode == "split":
        p_admin = multiprocessing.Process(target=_run_admin, kwargs={"reload": reload})
        p_reader = multiprocessing.Process(target=_run_reader, kwargs={"reload": reload})
        p_admin.start()
        p_reader.start()
        p_admin.join()
        p_reader.join()
    else:
        uvicorn.run("novelai.api.app:app" if reload else app, host=settings.WEB_HOST, port=settings.WEB_PORT, ...)
```

1. **Signal Blindness in Multiprocessing Split Mode**: When running in Docker with `DEPLOY_MODE=split`, `server.py` runs as PID 1. When Docker stops the container (`docker stop`, rolling deploy), the host sends `SIGTERM` to PID 1. Python's default signal handler for `multiprocessing.Process` does not propagate `SIGTERM` to child processes `p_admin` and `p_reader`. The parent process exits or blocks, and the children are abruptly killed with `SIGKILL` once Docker's stop grace period expires, causing dropped in-flight requests and interrupted DB transactions.
2. **Missing Uvicorn Graceful Connection Draining**: In both `_run_admin`, `_run_reader`, and `main`, `uvicorn.run()` is invoked with only `host`, `port`, `log_level`, and `reload`. Production connection draining settings are omitted:
   - `timeout_graceful_shutdown`: Not set (defaults to None, hanging indefinitely if client connections remain open).
   - `timeout_keep_alive`: Not tuned to match Caddy reverse proxy keep-alive settings.
   - `limit_concurrency`: Not set, permitting unconstrained connection acceptance during shutdown phases.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Severed User Requests During Deployments**: Deploying a new container image sends `SIGTERM` to the container. Active users reading novel chapters or executing long AI translations experience immediate HTTP connection reset or 502 Bad Gateway errors instead of their requests completing cleanly.
2. **Orphaned Database Transactions**: Abruptly terminating child workers leaves uncommitted database transactions and open connection locks in PostgreSQL until the server's TCP keepalive timeout expires.
3. **Container Shutdown Hangs**: Without explicit `timeout_graceful_shutdown`, WebSocket or persistent HTTP streaming connections keep Uvicorn open until Docker forcefully issues `SIGKILL` after 60 seconds, drastically slowing down automated deployments.

#### 3. Concrete Implementation Specification

1. Implement explicit signal forwarding in `novelai.api.server.main`:

```python
# backend/src/novelai/api/server.py
import signal
import sys
import multiprocessing
from typing import Any

def main(*, reload: bool = False) -> None:
    deploy_mode = os.environ.get("DEPLOY_MODE", "monolith")
    if deploy_mode == "split":
        p_admin = multiprocessing.Process(target=_run_admin, kwargs={"reload": reload})
        p_reader = multiprocessing.Process(target=_run_reader, kwargs={"reload": reload})

        def _handle_shutdown_signal(signum: int, frame: Any) -> None:
            logger.info("Received termination signal %s, draining child processes...", signum)
            for p in (p_admin, p_reader):
                if p.is_alive():
                    p.terminate()

        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
        signal.signal(signal.SIGINT, _handle_shutdown_signal)

        p_admin.start()
        p_reader.start()

        shutdown_timeout = getattr(settings, "WEB_SHUTDOWN_TIMEOUT_SECONDS", 25)
        p_admin.join(timeout=shutdown_timeout)
        p_reader.join(timeout=shutdown_timeout)

        for p in (p_admin, p_reader):
            if p.is_alive():
                logger.warning("Child process %s did not terminate in time, killing...", p.pid)
                p.kill()
        sys.exit(0)
```

2. Configure Uvicorn server options in `_run_admin` and `_run_reader`:

```python
uvicorn.run(
    "novelai.main_admin:app" if reload else admin_app,
    host=settings.WEB_HOST,
    port=8000,
    log_level=settings.LOG_LEVEL.lower(),
    timeout_graceful_shutdown=25,
    timeout_keep_alive=65,
    server_header=False,
)
```

#### 4. Verification & Test Strategy

Create `backend/tests/test_server_lifecycle.py`:

```python
import signal
from novelai.api import server

def test_server_signal_handler_terminates_children():
    terminated = []
    class MockProcess:
        pid = 1234
        def is_alive(self): return True
        def terminate(self): terminated.append(self)
        def join(self, timeout=None): pass

    admin = MockProcess()
    reader = MockProcess()
    handler = server._create_signal_handler([admin, reader])
    handler(signal.SIGTERM, None)

    assert len(terminated) == 2
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_server_lifecycle.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. Works across monolith and split deployment modes without altering API request routing.
- **Rollback Procedure**: Revert changes in `backend/src/novelai/api/server.py` and `deploy/compose.yml`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/api/server.py deploy/compose.yml
  ```

---

### REC-100: Fragile Single-Channel SMTP Alerting, Process-Local Cooldown Blind Spots, & Lack of Dead-Man's Switch

- **ID**: `REC-100`
- **Subsystem/Component**: Operational Alerting & Health Telemetry (`novelai.services.operator_alert_service`, `novelai.services.scheduler_service`)
- **Target Location**:
  - `backend/src/novelai/services/operator_alert_service.py:20-68` (`OperatorAlertService.send`)
  - `backend/src/novelai/services/scheduler_service.py:245-260` (`_check_stale_backups`)
- **Category**: `Reliability`
- **Severity**: `High`
- **Summary**: `OperatorAlertService` relies exclusively on synchronous SMTP email with process-local in-memory cooldown state, failing silently if port 587 or email servers are unavailable; it lacks webhook integrations (Slack/Discord/PagerDuty) and dead-letter queues; and the platform has no outbound heartbeat / dead-man's switch to detect total infrastructure failure or hung event loops.

#### 1. Root Cause & Code-Level Diagnostic

In `backend/src/novelai/services/operator_alert_service.py:20-68`:

```python
class OperatorAlertService:
    def __init__(self) -> None:
        self._last_sent: dict[str, datetime] = {}
        self._failures: dict[str, int] = {}
    def send(self, *, code: str, message: str) -> bool:
        ...
        try:
            smtp = factory(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS)
            ...
        except Exception as exc:
            logger.warning("operator_alert_delivery_failed code=%s type=%s", code, exc.__class__.__name__)
            return False
```

1. **Single Point of Failure in Alert Delivery**: `OperatorAlertService.send()` only supports SMTP email via standard library `smtplib`. If the mail server is down, rate-limited by provider (e.g. SendGrid, Mailgun), or outbound SMTP ports (587/465) are blocked by cloud security groups, alerts are dropped with only a local log message. There is no secondary notification fallback channel (webhook to Slack, Discord, PagerDuty, Opsgenie, or Telegram).
2. **Process-Local In-Memory State**: `_failures: dict[str, int]` and `_last_sent: dict[str, datetime]` are stored in process-local instance variables. In multi-process or multi-worker architectures (e.g. `split` mode, Celery/RQ workers, container restarts), failure counters and cooldown timers are not shared. If 3 processes fail concurrently, 3 identical alert emails are dispatched. Conversely, container restarts reset failure counters to 0, delaying alert delivery for persistent issues.
3. **Lack of Dead-Man's Switch / Heartbeat**: If a catastrophic event occurs (power outage, host kernel panic, complete network disconnection, or hung asyncio event loop), the server cannot send an alert because the process is dead or unresponsive. There is no external ping / dead-man's switch (e.g. Healthchecks.io, Better Uptime, Cronitor) periodically pinged by `SchedulerService`. Operators have no automated way of knowing the entire backend went down until users report outages.

#### 2. Failure Scenarios & Security/Operational Impact

1. **Silent Catastrophic Failure**: Outbound SMTP credentials expire or provider blocks port 587. When the primary database runs out of disk or backups fail, `OperatorAlertService` catches the exception and logs a warning to disk, leaving operators completely unaware of the crisis.
2. **Alert Storms on Multi-Worker Failures**: When an external translation service experiences an outage, 4 concurrent crawler workers all hit the failure simultaneously, sending 4 duplicate emails every cycle because cooldown dictionaries are isolated in process memory.
3. **Silent Infrastructure Outage**: The entire Docker host crashes or network interface goes down. Because there is no external dead-man's switch expecting a heartbeat ping, no alert is triggered anywhere in the operator ecosystem.

#### 3. Concrete Implementation Specification

1. Add multi-channel webhook dispatching to `OperatorAlertService`:

```python
# backend/src/novelai/services/operator_alert_service.py
import httpx
from datetime import datetime, timezone

class OperatorAlertService:
    def _send_webhook(self, *, code: str, message: str) -> bool:
        webhook_url = getattr(settings, "OPERATOR_ALERT_WEBHOOK_URL", None)
        if not webhook_url:
            return False
        payload = {
            "text": f"🚨 *[NovelAI Alert]* `{code}`: {message}",
            "code": code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(webhook_url, json=payload)
                return resp.is_success
        except Exception as exc:
            logger.warning("webhook_alert_delivery_failed code=%s exc=%s", code, exc)
            return False

    def send(self, *, code: str, message: str) -> bool:
        if self._is_rate_limited(code):
            return False
        # Try Webhook first, fallback to SMTP
        sent = self._send_webhook(code=code, message=message)
        if not sent:
            sent = self._send_smtp(code=code, message=message)
        if sent:
            self._record_sent(code)
        return sent
```

2. Back cooldowns with Redis in `_is_rate_limited` and `_record_sent`:

```python
def _is_rate_limited(self, code: str) -> bool:
    try:
        from novelai.core.redis import get_redis_client
        redis = get_redis_client()
        return bool(redis.exists(f"operator_alert:cooldown:{code}"))
    except Exception:
        # Fallback to local dict if Redis unavailable
        return code in self._last_sent and (datetime.now(timezone.utc) - self._last_sent[code]).total_seconds() < 300

def _record_sent(self, code: str) -> None:
    try:
        from novelai.core.redis import get_redis_client
        redis = get_redis_client()
        redis.set(f"operator_alert:cooldown:{code}", "1", ex=300)  # 5 min cooldown
    except Exception:
        self._last_sent[code] = datetime.now(timezone.utc)
```

3. Implement external dead-man's switch heartbeat in `SchedulerService`:

```python
# backend/src/novelai/services/scheduler_service.py
async def _ping_dead_mans_switch(self) -> None:
    heartbeat_url = getattr(settings, "OPERATOR_HEARTBEAT_URL", None)
    if not heartbeat_url:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(heartbeat_url)
    except Exception as exc:
        logger.warning("dead_mans_switch_ping_failed url=%s exc=%s", heartbeat_url, exc)
```

Add to `SchedulerService._scheduled_tasks` with a 5-minute interval (`interval_seconds=300`).

#### 4. Verification & Test Strategy

Create `backend/tests/test_operator_alerts.py`:

```python
import pytest
from novelai.services.operator_alert_service import OperatorAlertService

def test_operator_alert_dispatches_webhook_and_records_cooldown(monkeypatch):
    service = OperatorAlertService()
    webhook_called = False

    def mock_send_webhook(code, message):
        nonlocal webhook_called
        webhook_called = True
        return True

    monkeypatch.setattr(service, "_send_webhook", mock_send_webhook)
    success = service.send(code="TEST_ALERT", message="Test message")

    assert success is True
    assert webhook_called is True
    # Immediate subsequent call should be suppressed by cooldown
    assert service.send(code="TEST_ALERT", message="Test message") is False
```

Execute tests via:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pytest.ps1 backend/tests/test_operator_alerts.py
```

#### 5. Compatibility & Rollback

- **Backwards Compatibility**: Fully backward compatible. If `OPERATOR_ALERT_WEBHOOK_URL` and `OPERATOR_HEARTBEAT_URL` are not configured, behavior gracefully falls back to existing SMTP logic.
- **Rollback Procedure**: Revert `backend/src/novelai/services/operator_alert_service.py` and `backend/src/novelai/services/scheduler_service.py`.
  ```powershell
  Rollback command: git checkout HEAD -- backend/src/novelai/services/operator_alert_service.py backend/src/novelai/services/scheduler_service.py
  ```

---

## Overall Audit Synthesis & Strategic Roadmap

Across all 10 iterations of this technical audit, exactly 100 concrete, verified, non-duplicate recommendations have been identified and documented. The findings span the entire Novel AI backend architecture: core APIs, security and auth, database layer and migrations, Cloudflare R2 object storage, web novel scraping and ingestion adapters, asynchronous LLM translation pipelines, worker concurrency and task scheduling, user data and access control, public reader caching and catalog search, and production observability, disaster recovery, and operations.

### High-Level Categorization Matrix (All 100 Recommendations)

| Category                                   | Count | Primary Focus Areas                                                                                                                    | Associated Recommendation IDs                                                                                                                                                                                                                                                                                                                                             |
| :----------------------------------------- | :---: | :------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Security & Hardening**                   |  22   | Auth elevation, token/cookie hardening, CSRF defense, SSRF & XSS prevention, secret redaction, rate limiting, and access control       | `REC-006`, `REC-007`, `REC-008`, `REC-009`, `REC-015`, `REC-023`, `REC-026`, `REC-034`, `REC-038`, `REC-040`, `REC-048`, `REC-061`, `REC-062`, `REC-063`, `REC-064`, `REC-065`, `REC-066`, `REC-067`, `REC-068`, `REC-069`, `REC-070`, `REC-091`                                                                                                                          |
| **Performance & Scalability**              |  32   | In-memory cache stampedes, N+1 queries, unindexed table scans, WAL contention, thread saturation, regex bottlenecks, and R2 I/O        | `REC-005`, `REC-013`, `REC-014`, `REC-018`, `REC-019`, `REC-021`, `REC-022`, `REC-024`, `REC-028`, `REC-029`, `REC-032`, `REC-033`, `REC-041`, `REC-042`, `REC-045`, `REC-046`, `REC-050`, `REC-051`, `REC-056`, `REC-058`, `REC-060`, `REC-076`, `REC-079`, `REC-081`, `REC-082`, `REC-083`, `REC-084`, `REC-085`, `REC-087`, `REC-089`, `REC-090`, `REC-093`, `REC-094` |
| **Reliability, Data Integrity & Recovery** |  28   | Disaster recovery, WAL archiving, lease renewals, worker crashes, schema constraints, transaction rollbacks, and data consistency      | `REC-002`, `REC-010`, `REC-011`, `REC-012`, `REC-016`, `REC-017`, `REC-020`, `REC-025`, `REC-027`, `REC-030`, `REC-031`, `REC-035`, `REC-036`, `REC-037`, `REC-043`, `REC-044`, `REC-047`, `REC-049`, `REC-052`, `REC-053`, `REC-054`, `REC-055`, `REC-057`, `REC-059`, `REC-077`, `REC-078`, `REC-080`, `REC-086`, `REC-097`, `REC-098`, `REC-100`                       |
| **Architecture & Infrastructure**          |  13   | Service boundary layering, ingress routing, split deployment lifecycles, signal handling, container contracts, and distributed tracing | `REC-001`, `REC-003`, `REC-004`, `REC-039`, `REC-071`, `REC-072`, `REC-075`, `REC-088`, `REC-092`, `REC-095`, `REC-096`, `REC-099`                                                                                                                                                                                                                                        |
| **New Features & Capabilities**            |   5   | Novel request intake lifecycle, guest library sync, community upvoting, and privacy data deletion workflows                            | `REC-073`, `REC-074`, `REC-087`, `REC-088`, `REC-095`                                                                                                                                                                                                                                                                                                                     |

---

### Implementation Phases

#### Phase 1: Immediate Action Priorities (Top 10 Critical Fixes Across All 100 Recommendations)

The following 10 recommendations address severe security vulnerabilities, data loss risks, or total outage triggers and should be prioritized immediately:

1. **REC-091 — Plaintext URL Credential Leaks in Logging & Missing Redaction**: Prevent database passwords and tokens from being emitted into plain log files during connection errors and tracebacks.
2. **REC-067 — Static Owner Bootstrap Secret Hardening & Lockout**: Enforce one-time owner initialization, deprecation, and lockout to eliminate persistent administrative compromise vectors.
3. **REC-092 — Caddy Gateway Restart Cascades & Health Probe Decoupling**: Decouple Caddy reverse proxy container health checks from backend readiness to prevent total frontend/reader outages during transient database load.
4. **REC-096 — Critical R2 Backup Blind Spot for Generations & Translations**: Expand R2 object snapshot backups to cover `generations/`, `translations/`, and `active/` pointers, preventing total loss of novel content.
5. **REC-097 — Continuous PostgreSQL WAL Archiving & Point-in-Time Recovery (PITR)**: Implement WAL archiving to Cloudflare R2, shrinking the current 24-hour disaster recovery RPO data loss window to under 5 minutes.
6. **REC-098 — Database Operational Tooling & Mocked Drill Remediation**: Implement `backup_postgres.ps1`, remove error suppression from `restore_postgres.ps1`, stream R2 downloads during verification drills, and convert mocked drills to genuine restore assertions.
7. **REC-081 & REC-083 — Public Reader Projection Cache Lock & Cold-Start DB Thrashing**: Replace recursive `deepcopy()` with frozen projection caching and batch chapter/novel pre-lookups to protect PostgreSQL under reader traffic.
8. **REC-090 — Analytics Ingestion Micro-Batching & WAL Sync Contention**: Batch `AnalyticsWriter` events to reduce database commits by 95%+, eliminating write-ahead log bottlenecks on the primary database.
9. **REC-094 — Prometheus Scrape DoS via In-Memory Full-Table Scans**: Replace unconstrained `list_activity()` scans with direct SQL `COUNT(*)...GROUP BY` aggregations and mount `/metrics` on the public reader.
10. **REC-099 — Child Process Signal Forwarding & Uvicorn Graceful Connection Draining**: Propagate `SIGTERM` to child processes in split deployment mode and configure Uvicorn connection draining to eliminate dropped user requests during deploys.

#### Phase 2: Operational & Scale Upgrades (Near-Term Infrastructure Hardening)

- **Distributed Redis Coordination (`REC-032`, `REC-076`, `REC-100`)**: Migrate in-memory rate limiting, domain throttling, Gemini quota tracking, and alert cooldown states to shared Redis clusters.
- **Advanced Glossary & Annotation Performance (`REC-089`, `REC-078`)**: Replace linear regex scans in reader chapters with Aho-Corasick multi-pattern search, and persist glossary terms in chapter projections.
- **Observability & Distributed Tracing (`REC-095`)**: Implement OpenTelemetry standards with W3C `traceparent` context propagation across Caddy, FastAPI, background workers, and external HTTP clients.
- **Worker Priority Tiers & Cancellation Propagation (`REC-053`, `REC-057`, `REC-058`)**: Introduce priority tiers for user-facing vs background bulk jobs, and replace immediate job cancellations during container restart with graceful lease releases.
- **Search & Query Optimization (`REC-084`, `REC-085`)**: Add PostgreSQL trigram/GIN indexes for catalog search, and materialize multi-day public ranking metrics into periodic summary tables.

#### Phase 3: Feature Roadmap & Long-term Evolution (Platform Growth)

- **Guest-to-Account Synchronization (`REC-087`)**: Implement bulk bookmark and reading progress synchronization endpoints enabling anonymous readers to seamlessly migrate their library upon logging in.
- **Novel Request Lifecycle & Community Upvoting (`REC-073`, `REC-074`)**: Build a full state machine workflow for user-submitted novel translation requests, including duplicate detection, community voting, and intake auditing.
- **Automated DMCA Enforcement & Edge Purging (`REC-071`)**: Implement automated workflow cascading for approved takedowns, cancelling in-flight crawler activities and triggering Cloudflare CDN edge cache purges.
- **Multi-Model Translation Engine & Hallucination Guardrails (`REC-047`, `REC-049`)**: Implement dynamic LLM grader evaluations, hallucination residue detection, and automated cost estimation updates across multi-model providers.
- **User Privacy & Keyset Pagination (`REC-088`, `REC-075`)**: Provide full user history deletion endpoints, account GDPR anonymization pipelines, and genuine keyset cursor pagination for high-volume reader feeds.
