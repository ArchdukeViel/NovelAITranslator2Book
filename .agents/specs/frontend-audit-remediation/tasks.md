# Frontend Audit Remediation Tasks (Strict Contract Mode)

Spec ID: frontend-audit-remediation
Version: 1.2.0
Status: Complete
Updated: 2026-09-06

## Tasks

- [x] **T-000 Baseline preflight and workspace verification**
  - Maps to: none
  - Depends on: none
  - State: complete
  - Authorization: Local workspace inspection
  - Scope: Repository status and baseline checks
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/docs-check.ps1; if ($?) { git status --short }`
  - Expected: Clean verification with docs-check passing
  - Attempts: 1
  - Last result: passed (exit 0) - docs-check 0 violations
  - Evidence: tools/docs-check.ps1 exit 0; git status --short verified

- [x] **T-001 Escape JSON-LD serialization in novel detail page (Resolves Finding 1.1)**
  - Maps to: REQ-1, AC-1, SEC-2
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/app/(public)/novels/[slug]/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Select-String -LiteralPath 'frontend/app/(public)/novels/[slug]/page.tsx' -Pattern 'JSON\.stringify\(jsonLd\)\.replace'"`
  - Expected: Matches JSON-LD replacement pattern with exit code 0
  - Attempts: 1
  - Last result: passed (exit 0) - line 417 matched
  - Evidence: frontend/app/(public)/novels/[slug]/page.tsx:417 JSON.stringify(jsonLd).replace(/</g, "\\u003c")

- [x] **T-002 Accessible modal and token TTL for contributor credentials (Resolves Findings 1.2, 8.1)**
  - Maps to: REQ-2, REQ-13, AC-2, AC-13, SEC-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/app/(public)/account/contributions/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Select-String -LiteralPath 'frontend/app/(public)/account/contributions/page.tsx' -Pattern 'window\.confirm'"`
  - Expected: Zero matches found for window.confirm
  - Attempts: 1
  - Last result: passed (0 matches)
  - Evidence: frontend/app/(public)/account/contributions/page.tsx updated with ConfirmDialog and 30-day localStorage token TTL lifecycle; verified in app/(public)/account/contributions/__tests__/contributions.test.ts (4 passed)

- [x] **T-003 Harden safeRelativeReturnPath and cookie attribute security (Resolves Findings 1.3, 8.8)**
  - Maps to: REQ-3, REQ-14, AC-3, AC-14, SEC-1, SEC-2
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/lib/public-api.ts`, `frontend/lib/cookie-utils.ts`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Set-Location frontend; if ($?) { npx vitest run lib/public-api.test.ts; if ($?) { Set-Location .. } }"`
  - Expected: Public API and cookie helper tests pass with exit code 0
  - Attempts: 1
  - Last result: passed (8 passed in lib/public-api.test.ts)
  - Evidence: frontend/lib/public-api.ts safeRelativeReturnPath trims whitespace/control chars and rejects //, /\, \ prefixes; frontend/lib/cookie-utils.ts created with SameSite=Lax; path=/ + Secure-on-HTTPS; frontend/lib/public-api.test.ts covers AC-3/AC-14

- [x] **T-004 Throttle scroll event listeners in header and reader with requestAnimationFrame (Resolves Findings 2.3, 7.1, 7.2)**
  - Maps to: REQ-4, AC-4, NFR-3
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/components/public/public-header.tsx`, `frontend/app/(public)/novels/[slug]/chapter/[chapterId]/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Set-Location frontend; if ($?) { npx vitest run components/public/public-header.test.tsx; if ($?) { Set-Location .. } }"`
  - Expected: Header and reader test suites pass with exit code 0
  - Attempts: 1
  - Last result: passed (3 passed in public-header.test.tsx; 16 passed in chapter tracking+prefetch suites)
  - Evidence: public-header.tsx uses ticking-guarded requestAnimationFrame with passive listener and cancelAnimationFrame cleanup; chapter page throttles progress updates identically; new frontend/components/public/public-header.test.tsx covers passive registration, single-frame coalescing, unmount cancel

- [x] **T-005 Guard reader keyboard shortcuts against active input focus (Resolves Finding 2.8)**
  - Maps to: REQ-5, AC-5, NFR-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/components/public/reader-controls.tsx`, `frontend/app/(public)/novels/[slug]/chapter/[chapterId]/page.tsx`
  - Verification: `npx vitest run components/public/__tests__/reader-controls.test.tsx` (from `frontend/`)
  - Expected: Reader controls test suite passes with exit code 0
  - Attempts: 1
  - Last result: passed (6 passed in reader-controls.test.tsx; spec-listed path omits __tests__ and matches no files)
  - Evidence: exported isEditableTarget (INPUT/TEXTAREA/SELECT/isContentEditable/closest contenteditable) gates the "." shortcut; chapter ArrowLeft/ArrowRight guard extended identically; new editable-focus regression test added

- [x] **T-006 Add plain-text recovery fallback to reader error boundary (Resolves Finding 3.1)**
  - Maps to: REQ-6, AC-6, NFR-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/components/reader/reader-error-boundary.tsx`, `frontend/app/(public)/novels/[slug]/chapter/[chapterId]/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Set-Location frontend; if ($?) { npx vitest run components/reader/reader-error-boundary.test.tsx; if ($?) { Set-Location .. } }"`
  - Expected: Reader error boundary tests pass with exit code 0
  - Attempts: 1
  - Last result: passed (3 passed in reader-error-boundary.test.tsx, 0 unhandled errors)
  - Evidence: boundary gains plainText prop + showPlainText state with View plain text secondary action, Try rich view again, and Return to table of contents (/novels/[slug]); chapter page passes data.text; new test file covers all three tiers

- [x] **T-007 Propagate default AbortSignal timeout on public API fetch (Resolves Finding 3.6)**
  - Maps to: REQ-7, AC-7, NFR-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/lib/public-api.ts`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Set-Location frontend; if ($?) { npx vitest run lib/public-api.test.ts; if ($?) { Set-Location .. } }"`
  - Expected: Public API fetch tests pass with exit code 0
  - Attempts: 2
  - Last result: passed (11 passed in lib/public-api.test.ts; 2 passed in lib/__tests__/public-fetch-timeout.test.ts)
  - Evidence: PUBLIC_REQUEST_TIMEOUT_MS raised 10s to 15s; createRequestSignal combines caller + timeout legs via native AbortSignal.any and keeps caller/timeout attribution; timeout leg uses setTimeout-backed AbortController (noted in code) because native AbortSignal.timeout ignores vitest fake timers — first attempt with AbortSignal.timeout timed out the shared-timeout test under fake timers, reverted to deterministic hybrid

- [x] **T-008 Partition UI store into reader and admin namespaces with legacy migration (Resolves Finding 4.1)**
  - Maps to: REQ-8, AC-8, NFR-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/lib/store.ts`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Set-Location frontend; if ($?) { npx vitest run lib/store.test.ts; if ($?) { Set-Location .. } }"`
  - Expected: Store test suite passes with exit code 0
  - Attempts: 1
  - Last result: passed (5 passed in lib/store.test.ts; 3+5 passed in rewritten store property suites; typecheck 0 errors)
  - Evidence: useUiStore deleted; useReaderUiStore (dokushodo-reader-ui: theme/fontSize/width) and useAdminUiStore (dokushodo-admin-ui: darkMode/sidebarCollapsed) with novelai-ui purge on boot; reader-prefs.ts removed and its 2 consumers + 4 test mocks moved to useReaderUiStore; admin-shell uses useAdminUiStore; dead useUiStore import removed from lib/api.ts; zero remaining useUiStore/reader-prefs refs

- [x] **T-009 Enforce server-side layout auth redirect in admin root (Resolves Finding 5.1)**
  - Maps to: REQ-9, AC-9, SEC-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/app/(admin)/admin/layout.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Select-String -Path 'frontend/app/(admin)/admin/layout.tsx' -Pattern 'AdminAuthGuard|redirect'"`
  - Expected: Admin layout matches auth guard pattern with exit code 0
  - Attempts: 1
  - Last result: passed (4 pattern matches: redirect import/call, AdminAuthGuard import/usage)
  - Evidence: layout is now an async server component checking cookies().get("novelai_session") and redirect("/") when absent; AdminAuthGuard retained for client navigations; REQ-9 updated because no /admin/login route exists (a target under /admin/* would loop against this layout)

- [x] **T-010 Wrap search parameters in browse novels with Suspense boundary (Resolves Finding 5.3)**
  - Maps to: REQ-10, AC-10, NFR-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/app/(public)/browse-novels/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Select-String -Path 'frontend/app/(public)/browse-novels/page.tsx' -Pattern 'Suspense'"`
  - Expected: Matches Suspense boundary usage with exit code 0
  - Attempts: 1
  - Last result: passed (3 Suspense matches in browse-novels/page.tsx)
  - Evidence: page wraps BrowsePage in Suspense fallback BrowseNovelsSkeleton; inner BrowseContent (the useSearchParams consumer) was already suspended via BrowsePage LoadingState, so search-params ingestion is now doubly bounded

- [x] **T-011 Set explicit type=button default on Button component (Resolves Finding 6.1)**
  - Maps to: REQ-11, AC-11, NFR-1
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/components/ui/button.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Select-String -Path 'frontend/components/ui/button.tsx' -Pattern 'type = "button"'"`
  - Expected: Matches type="button" default with exit code 0
  - Attempts: 1
  - Last result: passed (pattern matched; 2 passed in new components/ui/button.test.tsx)
  - Evidence: Button destructures type = "button" with explicit type passthrough; overrides to submit/reset verified; owner-login and browse metadata suites unaffected (12 passed across 3 files)

- [x] **T-012 Lazy-load Recharts bundle in admin analytics page (Resolves Finding 7.5)**
  - Maps to: REQ-12, AC-12, NFR-1
  - Depends on: T-000
  - State: complete (stale finding, closed as moot per owner decision 2026-09-06)
  - Authorization: Local code modification (no dependency addition required)
  - Scope: `frontend/app/(admin)/admin/analytics/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Select-String -Path 'frontend/app/(admin)/admin/analytics/page.tsx' -Pattern 'dynamic'"`
  - Expected: No dynamic import needed; page uses no Recharts
  - Attempts: 1
  - Last result: passed (0 Recharts refs repo-wide; analytics page renders plain HTML tables; "dynamic" pattern not present because the absent bundle does not need splitting)
  - Evidence: closure path documented in design.md Subsystem 11. NFR-4 invariant ("Recharts charting library must be loaded dynamically on demand, reducing initial bundle weight") is vacuously satisfied — there is no Recharts bundle in the initial admin chunk. If charting is reintroduced, the documented next/dynamic({ssr:false}) pattern in design.md Subsystem 11 is the standing solution.

- [x] **T-013 Implement magic-byte verification in cover image uploader (Resolves Finding 9.3)**
  - Maps to: REQ-15, AC-15, SEC-2
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification (absorbed into this spec per owner decision 2026-09-06)
  - Scope: `frontend/lib/cover-magic-bytes.ts`, `frontend/components/admin/cover-uploader.tsx`, `frontend/components/admin/library/library-row-actions.tsx`, `frontend/app/(admin)/admin/library/page.tsx`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Set-Location frontend; if ($?) { npx vitest run components/admin/cover-uploader.test.tsx; if ($?) { Set-Location .. } }"`
  - Expected: Cover uploader test suite passes with exit code 0
  - Attempts: 1
  - Last result: passed (16 passed: 9 in cover-magic-bytes.test.ts + 7 in cover-uploader.test.tsx; 32 passed across uploader + publish-controls + library-page suites)
  - Evidence: pure validator (cover-magic-bytes.ts) accepts PNG/JPEG/WEBP signatures, rejects HTML/script/MZ/RIFF-non-WEBP files with typed reason; CoverUploader component wires readFileHeader + validateImageMagicBytes into a file input, surfaces a green/amber/red UI state per outcome, and the security invariant is asserted by a test (no `fetch` calls during validation, `onValidatedFile` not called for rejected files). Per-novel uploader drawer integrated into LibraryRowActions (per owner placement choice); page passes validated file to a console.info stub (transport wire-up is a follow-up product task). publish-controls.test.tsx fixtures updated for the new required props.

- [x] **T-014 Align publication_status domain union type with backend schema (Resolves Finding 10.1)**
  - Maps to: REQ-16, AC-16, NFR-2
  - Depends on: T-000
  - State: complete
  - Authorization: Local code modification
  - Scope: `frontend/lib/public-types.ts`, `frontend/lib/api-types.ts`, `frontend/components/public/{browse-page,status-badge}.tsx`, `backend/src/novelai/sources/status.py`, `backend/tests/test_sources_status.py`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "npm --prefix frontend run typecheck"` + `tools/pytest.ps1 -- backend/tests/test_sources_status.py`
  - Expected: TypeScript typecheck passes with 0 errors; backend tests pass
  - Attempts: 1
  - Last result: passed (tsc 0 errors; 22 passed in test_sources_status.py; 76 passed in lib/public-types.test.ts + novel-card + browse-page suites; ruff+pyright clean on changed backend files)
  - Evidence: 5-variant PublicationStatus union (completed|ongoing|hiatus|cancelled|unknown) aligned bidirectionally with backend PUBLICATION_STATUS_VALUES; backend adds conservative cancelled marker set (cancelled/canceled/abandoned/discontinued/dropped + 連載中止/中止/打ち切り/休載中/連載停止/更新停止) with order-of-precedence completed>cancelled>hiatus>ongoing; frontend StatusBadge adds red tone for cancelled; toPublicationStatus already handles the 5th variant case-insensitively.

- [x] **T-015 Full regression verification and documentation check**
  - Maps to: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16
  - Depends on: T-001, T-002, T-003, T-004, T-005, T-006, T-007, T-008, T-009, T-010, T-011, T-012, T-013, T-014
  - State: complete
  - Authorization: Local verification
  - Scope: End-to-end frontend + status normalizer regression
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/docs-check.ps1; if ($?) { npm --prefix frontend run test; if ($?) { powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 -- backend/tests/test_sources_status.py } }`
  - Expected: All test suites pass and docs check passes with 0 violations; backend normalizer tests pass
  - Attempts: 1
  - Last result: passed
  - Evidence: docs-check exit 0, 0 violations; eslint 0 errors/0 warnings; tsc 0 errors; ruff+pyright clean on changed backend files; full frontend suite 94 files / 941 tests passed (was 92/925 at first close — 16 added: 9 cover-magic-bytes.test.ts + 7 cover-uploader.test.tsx); backend status normalizer tests 22/22 passed; backend sibling tests 147/147 passed (kakuyomu/generic/novel18/syosetu/migrate/catalog_service); graphify index rebuilt (17,791 nodes, 44,130 edges).
