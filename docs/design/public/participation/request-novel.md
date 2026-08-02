# Participation — Request Novel Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | participation |
| Routes | `/request-novel` |
| Design status | approved target |
| Implementation status | drifted (UI partial: URL input disabled on landing, auth gate wraps table) |
| Active work | `DEBT-FE-01` (`WORK.md`) |
| Implementation | `frontend/app/(public)/request-novel/page.tsx`, `frontend/components/public/request-control.tsx`, `frontend/app/(public)/account/requests/page.tsx` |

## Purpose
Public page for requesting new Japanese web novels to be ingested and translated into Dokushodo.

## User Goal
Submit a link to an unindexed web novel from Kakuyomu or Syosetu so operators can review, crawl, and add it to the catalog.

## Audience and Permissions
- **Guests:** May view page instructions, supported sources list, and fill out the request form.
- **Authenticated Users (`role="user"` / `role="owner"`):** May submit requests and view request history.

## Primary Action
"Submit Request" button.

## Approved Target vs Current Implementation Drift Audit

### Approved Target Contract
1. Guest may view and fill the request form on `/request-novel`.
2. Form submission requires authentication; unauthenticated submission triggers a sign-in detour (`/login?next=/request-novel`).
3. Entered form data (source URL, optional details) survives authentication detour in local session storage as a draft.
4. Returning to the form after successful sign-in restores the draft automatically.
5. Restored draft is **not** silently auto-submitted; the user must explicitly confirm final submission.
6. Supported sources: Kakuyomu, Syosetu, Syosetu18.

### Actual Current Implementation Verification
1. `frontend/app/(public)/request-novel/page.tsx` renders a hardcoded `<input disabled placeholder="https://kakuyomu.jp/..." />` with the caption "URL submission is not open yet."
2. Request history table on `/request-novel/page.tsx` is wrapped inside `<AuthGate>`, hiding the entire content area for guest visitors.
3. Functional request submission and request history exist separately inside `frontend/components/public/request-control.tsx` and `frontend/app/(public)/account/requests/page.tsx` for authenticated users.

### Drift Summary
`/request-novel/page.tsx` landing surface has drifted into a disabled placeholder, while active request capability lives on `/account/requests`. Tracked as `DEBT-FE-01` in `WORK.md`.

## Required Page States

1. **Initial / Form Ready:** Form displayed with clean URL and details inputs.
2. **Valid URL:** User enters valid HTTP/HTTPS URL from supported source (Kakuyomu, Syosetu, Syosetu18).
3. **Validating:** Client-side URL parsing or backend validation in progress.
4. **Unsupported Source Error:** Displayed when URL hostname does not match supported domains. Copy: *"This source is unsupported."*
5. **Duplicate Novel Warning:** URL resolves to a novel already present in the catalog. Copy: *"This novel already exists in the catalog."*
6. **Existing Request Warning:** Active request already pending for this URL. Copy: *"A request already exists for this novel."*
7. **Authentication Required Notice:** Guest attempts submission. Copy: *"You must sign in to submit a request."*
8. **Draft Restored After Authentication:** Returning from auth detour with restored draft values.
9. **Submitting:** Async request submission in flight with spinner indicator.
10. **Submitted Success:** Submission accepted and pending operator review. Copy: *"Request submitted successfully."*
11. **Submission Globally Unavailable:** Form disabled during administrative maintenance or request freezes. Copy: *"Request submissions are temporarily closed."*
12. **Rate Limited Notice:** User has exceeded submission quota.
13. **Recoverable API Failure:** Network or server error during submit with retry CTA.
14. **Request History Loading:** Skeleton indicator for past request log.
15. **Request History Empty:** Reader has submitted no prior requests.
16. **Request History Populated:** Table of user's past requests with status indicators.

## Information Hierarchy & Anatomy
1. Page Header (Title: "Request Novel", Subtitle & Instructions)
2. Main Content Column: Request Form (`RequestControl`) + Request History Log
3. Sidebar Column: Supported Sources Card + Usage & Moderation Guidelines Card

## Copy & Accessibility Rules
- Explicit error copy distinguishing:
  - "You must sign in"
  - "This source is unsupported"
  - "This novel already exists"
  - "A request already exists"
  - "Request submissions are temporarily closed."
- Accessible form labels, aria-live status announcements, and full keyboard navigation.
