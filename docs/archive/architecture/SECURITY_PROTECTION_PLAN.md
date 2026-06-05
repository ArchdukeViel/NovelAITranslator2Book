# Archived Architecture Note

This historical document was consolidated into `docs/architecture/architecture.md`. It may contain stale implementation status and should not be used as current architecture guidance.

# Security Protection Plan

## Scope

This plan covers the current single-owner/admin NovelAI deployment. It does not introduce public users, public contribution credentials, owner/admin role separation, billing, database storage, or credential pooling.

## Protected Data Classification

Critical:
- provider API keys
- admin/session tokens
- encryption keys
- `.env` and deployment secret files
- backups and archives containing runtime state

High:
- raw scraped chapters
- parsed chapters
- translation chunks and temporary bundles
- provider request/response records
- unpublished translations
- job events and logs

Medium:
- published translated chapters
- public metadata
- public assets

## Implemented Baseline Protections

Path traversal:
- Storage-backed `novel_id`, `chapter_id`, checkpoint names, and export format suffixes reject traversal, absolute paths, Windows drive paths, UNC paths, URL-encoded traversal, and null bytes before becoming filenames.
- Stored asset paths are resolved under the owning novel directory and rejected if they escape that root.

Runtime storage isolation:
- `storage/novel_library` is not served directly as a static directory.
- Admin runtime-state metadata exposes stable runtime labels instead of absolute filesystem paths.
- Export endpoints build files through storage services and export only translated chapter text/images selected by storage readers.

Secret redaction:
- API error payloads redact common secret-bearing fields and text patterns.
- Logging formatters redact Authorization headers, cookies, API keys, admin tokens, passwords, and bearer tokens in messages, exceptions, and structured extra fields.
- Provider request persistence continues to strip secret-bearing headers and keys before writing records.

API error leak prevention:
- Known errors use the structured error envelope.
- Unknown 500 responses do not expose tracebacks by default.
- Storage errors no longer expose full exception text or absolute filenames in public details.

Source URL SSRF protection:
- FetchService URL validation allows only HTTP(S).
- Embedded URL credentials, localhost names, metadata hostnames, private/reserved/link-local/multicast/unspecified addresses, and loopback addresses are rejected before HTTP requests.
- Source adapters integrated with FetchService inherit this URL validation.

Backup and exclusion policy:
- `.env`, runtime storage, logs, local backup directories, and common archive/backup file extensions are ignored by git.
- Raw scraped chapters, provider request records, and runtime logs should not be committed unless intentionally sanitized for fixtures or documentation.

## Deferred Public Contribution Security

Public contribution credentials remain out of scope until the project explicitly adds:
- authenticated public users
- admin role separation
- encrypted credential storage
- revocation/deletion flows
- audit logging
- contribution consent and usage limits
- scheduler enforcement of credential scope
- separate public-user and admin credential management UIs

Until then, provider credentials are treated as single-owner/admin runtime secrets and must not be exposed as a public contribution pool.

## Remaining Risks

- Source adapters that have not yet been fully migrated to FetchService may still need review for URL validation consistency.
- Runtime provider response records can contain sensitive novel text by design and should remain private.
- The current file-backed runtime store has no multi-user access boundary.
- Backups remain operator-managed; encrypted backup handling is not implemented here.
- `DEBUG_ERRORS=true` should be used only in trusted local development because it intentionally expands error detail.
