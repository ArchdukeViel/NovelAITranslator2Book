# Glossary Approved Term Apply Plan

## 1. Purpose

This workflow repairs old saved translated chapters after the owner has approved
glossary decisions.

Approved glossary prompt injection already improves future translations, but it
does not change chapters that were translated before the decision existed. The
approved-term apply workflow gives the owner a controlled way to find old
variants in saved translated chapters, preview exact replacements, apply only
reviewed changes, and roll them back if needed.

This document is a plan only. It does not implement backend repair, frontend UI,
migrations, storage mutation, DB mutation, provider calls, scraping, translation,
or automatic chapter repair.

## 2. Core Safety Rule

Approving a glossary term changes glossary state only.

Saved chapter repair is a separate explicit owner action. The system must never
silently rewrite saved translated chapters when an entry is approved, edited, or
imported. Applying approved terms to saved chapter text must be previewed,
confirmed, backed up, auditable, and reversible.

## 3. Apply Workflow

The v1 workflow should be owner-initiated and staged:

1. Select one approved glossary entry or a small set of approved entries for one
   platform `novel_id`.
2. Scan saved translated chapters for affected old variants and old approved
   translations.
3. Produce a preview of exact replacement candidates without mutating storage.
4. Classify each match as safe, needs review, or blocked.
5. Show exact before/after snippets and replacement counts.
6. Owner confirms selected safe/reviewed replacements.
7. Create a backup/version record before writing changed chapter text.
8. Apply the replacement to the storage-backed translated chapter.
9. Record an audit/apply event for every affected chapter and glossary entry.
10. Expose rollback for each apply event or apply batch.

The default path should be preview-first. The apply endpoint should reject
requests that do not reference a prior preview token, preview hash, or equivalent
server-side validation record.

## 4. Matching Strategy

v1 should use exact replacement only.

Allowed match sources:

- Rejected, banned, deprecated, or observed aliases attached to the approved
  entry when they represent old translated variants.
- Previous approved translations for the same entry if the owner changed the
  approved translation.
- Explicit owner-provided old variant text in a future apply request, if the
  backend validates it against the selected entry and preview.

Rules:

- Match translated target text only for v1. Do not replace Japanese/source terms
  in translated output unless the owner explicitly selects such text from a
  translated chapter preview.
- Respect entry matching policy where it safely narrows exact matching.
- Prefer whole-term or phrase-boundary matches for Latin text.
- Treat case-sensitive terms conservatively. Default to exact case unless the
  entry or alias policy explicitly allows case-insensitive matching.
- Do not fuzzy-match, paraphrase, or infer replacements in v1.
- Do not call providers in v1.
- Do not run a natural-language rewrite in v1.
- Do not replace inside protected metadata, internal markers, or structured
  chapter annotations if those are present in storage text.

## 5. Risk Classification

Safe:

- Exact whole-term replacement in translated prose.
- One old variant maps to exactly one approved glossary entry.
- Replacement does not overlap another match.
- Replacement does not produce a banned or rejected variant.
- Chapter has a backup/version path available.

Needs review:

- Ambiguous substring, such as a name inside another word.
- Case-insensitive match where casing may matter.
- Multiple possible replacements are present but not directly conflicting.
- Current chapter already contains both the old and new term.
- Replacing a short token that could be a common word.
- Replacement touches punctuation-adjacent or title/header text.

Blocked:

- The same old variant maps to multiple approved entries.
- Replacement conflicts with another approved term.
- Replacement would create a banned or rejected alias.
- Match overlaps another selected replacement.
- Chapter text is missing, unreadable, or lacks a backup/version destination.
- Chapter is protected, locked, or currently being rewritten by another job.
- Preview hash no longer matches current saved chapter content.

## 6. Backup and Versioning

Before any write, the backend should preserve enough information to restore the
previous translated chapter exactly.

Backup/version data should include:

- Platform `novel_id`.
- DB `chapter_id` when available.
- Storage chapter key/reference.
- Original translated chapter text or an immutable storage backup pointer.
- Applied translated chapter text or applied version pointer.
- Timestamp.
- Glossary entry id.
- Operator/admin user id if available.
- Replacement count.
- Affected chapter id.
- Preview hash or source text hash used for confirmation.
- Rollback pointer.
- Rollback status.

Large chapter text should remain storage-backed. DB rows should store metadata,
hashes, storage keys, and audit state rather than unbounded chapter bodies unless
a migration explicitly chooses a compact text snapshot strategy.

## 7. Audit Trail

The audit trail should be DB-backed and queryable from admin UI.

Audit/apply event fields:

- Apply event id.
- Optional apply batch id.
- Novel id.
- Chapter id.
- Source/storage chapter reference.
- Glossary entry id.
- Old text.
- New text.
- Replacement count.
- Match classification at confirmation time.
- Status: previewed, applied, partially_applied, blocked, failed, rolled_back.
- Created by.
- Created at.
- Applied at.
- Rollback status.
- Rolled back by.
- Rolled back at.
- Error code/message, sanitized and without raw tracebacks.

Audit records should never include provider keys, secrets, raw filesystem paths,
or unbounded copyrighted excerpts.

## 8. Admin UI

The owner UI should make repair visibly separate from approval.

Recommended controls:

- "Find affected chapters" action on an approved glossary entry or selected
  approved entries.
- Preview table grouped by chapter.
- Before/after snippets around each exact match.
- Safe, Needs review, and Blocked badges.
- Filters for classification and selected entries.
- Apply selected.
- Rollback apply event.
- Link from apply event back to glossary entry and affected chapter.

The approval UI must not contain auto-apply behavior. Any repair UI should use
clear copy such as "Approving terms does not rewrite saved chapters" and "Apply
to saved chapters is previewed and reversible."

## 9. Backend API Plan

Routers should stay thin and delegate matching/apply logic to a service layer.

Possible owner-only endpoints:

- `POST /api/admin/novels/{novel_id}/glossary/apply/preview`
  - Body: selected glossary entry ids, optional chapter range/list, optional
    classification filters.
  - Result: preview id/hash, affected chapters, matches, classifications,
    replacement counts, warnings, blocked reasons.

- `POST /api/admin/novels/{novel_id}/glossary/apply/confirm`
  - Body: preview id/hash, selected match ids or chapter ids.
  - Result: apply batch id, created/updated backup records, applied event
    summaries, skipped/blocked counts.

- `GET /api/admin/novels/{novel_id}/glossary/apply/events`
  - Result: paginated apply/rollback history for the novel.

- `POST /api/admin/novels/{novel_id}/glossary/apply/events/{event_id}/rollback`
  - Body: optional rationale.
  - Result: rollback event status and restored chapter reference.

Every unsafe endpoint must require owner auth and CSRF. Apply/rollback endpoints
should validate that the target novel, glossary entry, chapter, and backup all
belong to the same platform `novel_id`.

## 10. Storage and DB Boundary

Current architecture keeps heavy chapter content storage-backed while metadata
and audit records are Postgres-backed.

Storage should own:

- Current translated chapter payload.
- Immutable backup copy or versioned translated chapter payload.
- Optional applied translated chapter version if versioning stores full copies.

DB should own:

- Apply preview metadata if persisted.
- Apply event metadata.
- Glossary entry and alias references.
- Chapter id/storage key references.
- Replacement counts.
- Text hashes.
- Rollback state.
- Created/applied/rolled-back operator metadata.

API responses should return ids, chapter numbers, snippets, classifications,
and storage-neutral references. They should not expose raw filesystem paths.

## 11. Conflict Behavior

Conflicts should block automatic apply and be visible in preview.

Cases:

- Two glossary entries target the same old variant.
  - Block the match unless the owner narrows to one entry and the backend can
    prove the target is unambiguous.

- Old variant maps to multiple approved terms.
  - Block and show all candidate approved entries.

- Replacement would create a banned variant.
  - Block and explain which banned/rejected alias would be produced.

- Current chapter already contains both old and new terms.
  - Classify as Needs review. The owner may apply selected exact instances, but
    the backend should not treat this as a fully safe chapter-wide replacement.

- Overlapping replacements.
  - Prefer longest exact match only if it belongs to a single approved entry;
    otherwise block.

- Approved term conflicts with another approved term.
  - Block and require glossary cleanup before chapter repair.

## 12. Testing Strategy

Required future tests:

- Preview does not mutate storage.
- Apply creates backup/version record before writing.
- Rollback restores previous translated chapter text exactly.
- Risky substring is not auto-applied.
- Conflicts block apply.
- Audit event is recorded.
- Approval does not trigger apply.
- Provider is not called.
- Scraping is not called.
- Translation is not called.
- Unrelated chapters are unchanged.
- Existing approved glossary entries remain approved.
- Apply validates platform `novel_id` ownership.
- Rollback validates platform `novel_id` ownership.
- Preview hash mismatch blocks stale apply.
- Missing backup destination blocks apply.

## 13. Rollout Order

Recommended implementation phases:

1. `GLOSSARY-APPROVED-TERM-APPLY-BACKEND-PREVIEW-1`
   - Service-only and API preview. No storage mutation.

2. `GLOSSARY-APPROVED-TERM-APPLY-BACKEND-APPLY-1`
   - Backup/version metadata and explicit apply endpoint.

3. `GLOSSARY-APPROVED-TERM-APPLY-ADMIN-UI-1`
   - Owner preview/apply UI with risk badges and snippets.

4. `GLOSSARY-APPROVED-TERM-APPLY-LIVE-SMOKE-1`
   - Live preview on a known novel, then one small reversible apply if approved.

5. `GLOSSARY-QA-SCANNER-1`
   - Separate scanner for old variants, missing approved terms, and consistency
     warnings after the repair workflow exists.

## 14. Non-Goals

v1 explicitly excludes:

- Provider rewrite.
- Fuzzy natural-language rewrite.
- Automatic chapter repair on approval.
- Public reader glossary popovers.
- User display overrides.
- Bulk unreviewed rewrite.
- Translation reruns.
- Source scraping.
- Prompt injection of Reviewing/candidate suggestions.
- Editing glossary approval state as part of chapter repair.
