# requirements.md

# Requirements: Launch Readiness Checklist

## Introduction

Launch readiness requires a single final checklist that verifies the system is safe, functional, observable, recoverable, and documented before public release. The checklist must cover product flows, public reader behavior, admin operations, security/privacy, takedown, backups, observability, performance, accessibility, SEO, production hardening, and rollback.

## Requirement 1: Launch checklist artifact

### User story

As an operator, I want one launch checklist artifact so final readiness is tracked in one place.

### Acceptance criteria

1. WHEN this spec is implemented THEN a launch readiness checklist SHALL exist.
2. WHEN checklist exists THEN it SHALL group checks by readiness category.
3. WHEN checklist item exists THEN it SHALL have status.
4. WHEN checklist item exists THEN it SHOULD have owner.
5. WHEN checklist item exists THEN it SHOULD have evidence or notes.
6. WHEN checklist item is blocked THEN blocker reason SHALL be recorded.
7. WHEN checklist item is waived THEN waiver owner and reason SHALL be recorded.
8. WHEN checklist is reviewed THEN final go/no-go decision SHALL be recorded.

## Requirement 2: Status model

### User story

As a release owner, I want consistent statuses so readiness is easy to understand.

### Acceptance criteria

1. WHEN a checklist item has not started THEN status SHALL be `not_started`.
2. WHEN a checklist item is underway THEN status SHALL be `in_progress`.
3. WHEN a checklist item is complete with no concerns THEN status SHALL be `passed`.
4. WHEN a checklist item is complete with acceptable notes THEN status SHALL be `passed_with_notes`.
5. WHEN a checklist item blocks launch THEN status SHALL be `blocked`.
6. WHEN a checklist item is intentionally accepted despite risk THEN status SHALL be `waived`.
7. WHEN a checklist item does not apply THEN status SHALL be `not_applicable`.
8. WHEN a blocked item exists THEN launch decision SHALL not be `GO` unless it is resolved or explicitly waived according to policy.

## Requirement 3: Core product flow verification

### User story

As a product owner, I want core workflows verified end-to-end before launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN create/import novel flow SHALL be verified.
2. WHEN launch checklist is run THEN crawl/fetch flow SHALL be verified.
3. WHEN launch checklist is run THEN scrape chapter flow SHALL be verified.
4. WHEN launch checklist is run THEN translation flow SHALL be verified.
5. WHEN launch checklist is run THEN translated chapter persistence SHALL be verified.
6. WHEN launch checklist is run THEN activity/progress visibility SHALL be verified.
7. WHEN launch checklist is run THEN publish/public reader flow SHALL be verified.
8. WHEN launch checklist is run THEN export generation flow SHALL be verified.
9. WHEN any core flow fails THEN launch SHALL be blocked unless explicitly out of scope and waived.

## Requirement 4: Translation and glossary readiness

### User story

As a translation quality owner, I want translation and glossary behavior verified before launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN JP→EN prompt policy SHALL be verified as current.
2. WHEN launch checklist is run THEN translation prompt tests or snapshots SHALL pass where available.
3. WHEN glossary terms exist THEN glossary injection SHALL be verified.
4. WHEN glossary diagnostics exist THEN diagnostics persistence SHALL be verified.
5. WHEN public glossary annotations are enabled THEN public-safe annotation behavior SHALL be verified.
6. WHEN annotation settings exist THEN global and per-novel settings SHALL be verified.
7. WHEN glossary revision invalidation exists THEN stale translation behavior SHALL be verified.
8. WHEN translation failure occurs THEN safe error handling SHALL be verified.

## Requirement 5: Public reader readiness

### User story

As a reader, I want public reader pages to work safely and reliably at launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN published public novel page SHALL load.
2. WHEN launch checklist is run THEN published public chapter page SHALL load.
3. WHEN content is unpublished THEN public access SHALL be blocked.
4. WHEN content is private THEN public access SHALL be blocked.
5. WHEN content is taken down THEN public access SHALL be blocked.
6. WHEN graceful degradation is triggered THEN public reader fallback behavior SHALL be verified.
7. WHEN public reader error/empty states occur THEN safe fallback UI SHALL be verified.
8. WHEN public reader cache is enabled THEN publication and takedown safety SHALL be verified.
9. WHEN any public reader safety check fails THEN launch SHALL be blocked.

## Requirement 6: Export readiness

### User story

As a user or admin, I want export generation and download behavior verified before launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN PDF exporter registration SHALL be verified.
2. WHEN launch checklist is run THEN export generation SHALL be verified.
3. WHEN launch checklist is run THEN export manifest recording SHALL be verified.
4. WHEN export freshness checks exist THEN stale/missing status behavior SHALL be verified.
5. WHEN admin export UI exists THEN manifest list/detail/re-export behavior SHALL be verified.
6. WHEN public downloads exist THEN they SHALL not expose private paths or signed URLs unsafely.
7. WHEN content is taken down THEN export/download access SHALL be blocked.
8. WHEN critical export path fails and exports are in launch scope THEN launch SHALL be blocked or waived.

## Requirement 7: Admin operations readiness

### User story

As an operator, I want admin tools verified so the system can be managed after launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN admin user management SHALL be verified.
2. WHEN launch checklist is run THEN admin audit log viewer SHALL be verified.
3. WHEN launch checklist is run THEN admin health page SHALL be verified.
4. WHEN metrics dashboard exists THEN admin metrics SHALL be verified.
5. WHEN analytics dashboard exists THEN admin analytics SHALL be verified.
6. WHEN backup/status page exists THEN admin backup status SHALL be verified.
7. WHEN maintenance status exists THEN admin maintenance status SHALL be verified.
8. WHEN takedown workflow exists THEN admin takedown review/action SHALL be verified.
9. WHEN non-admin accesses admin tools THEN access SHALL be blocked.

## Requirement 8: Security and privacy readiness

### User story

As a security owner, I want security and privacy checks completed before public launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN authentication requirements SHALL be verified.
2. WHEN launch checklist is run THEN admin authorization SHALL be verified.
3. WHEN launch checklist is run THEN session revocation SHALL be verified.
4. WHEN launch checklist is run THEN disabled-user access blocking SHALL be verified.
5. WHEN launch checklist is run THEN CORS/CSRF production safety SHALL be verified.
6. WHEN launch checklist is run THEN rate limits SHALL be verified.
7. WHEN launch checklist is run THEN secret exposure checks SHALL be verified.
8. WHEN launch checklist is run THEN log redaction SHALL be verified.
9. WHEN launch checklist is run THEN public API private-field exposure checks SHALL be verified.
10. WHEN any private content or secret exposure is found THEN launch SHALL be blocked.

## Requirement 9: Legal/takedown readiness

### User story

As an operator, I want legal/takedown handling verified before public launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN takedown intake SHALL be verified if enabled.
2. WHEN launch checklist is run THEN admin takedown review SHALL be verified.
3. WHEN launch checklist is run THEN takedown enforcement SHALL be verified.
4. WHEN takedown is active THEN public reader SHALL not serve content.
5. WHEN takedown is active THEN sitemap SHALL exclude content.
6. WHEN takedown is active THEN SEO noindex/unavailable behavior SHALL be verified.
7. WHEN takedown is active THEN exports/downloads SHALL be blocked.
8. WHEN takedown action occurs THEN audit logging SHALL be verified.
9. WHEN private legal details appear in public responses/logs THEN launch SHALL be blocked.

## Requirement 10: Performance readiness

### User story

As a reader, I want the public reader to meet launch performance expectations.

### Acceptance criteria

1. WHEN launch checklist is run THEN public reader request count SHALL be verified.
2. WHEN launch checklist is run THEN public reader bundle budget SHALL be checked or documented.
3. WHEN launch checklist is run THEN long chapter fixture SHALL be tested.
4. WHEN launch checklist is run THEN many-annotation fixture SHALL be tested if annotations are enabled.
5. WHEN launch checklist is run THEN cover image optimization SHALL be verified.
6. WHEN launch checklist is run THEN public cache behavior SHALL be verified.
7. WHEN performance budget is exceeded THEN exception or blocker SHALL be recorded.

## Requirement 11: Accessibility readiness

### User story

As a reader using assistive technology, I want the reader to be usable at launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN keyboard-only public reader flow SHALL be verified.
2. WHEN launch checklist is run THEN skip links SHALL be verified.
3. WHEN launch checklist is run THEN reader settings keyboard operation SHALL be verified.
4. WHEN launch checklist is run THEN chapter navigation keyboard operation SHALL be verified.
5. WHEN glossary annotations are enabled THEN keyboard access SHALL be verified.
6. WHEN launch checklist is run THEN headings and landmarks SHALL be verified.
7. WHEN launch checklist is run THEN 200% zoom SHALL be checked.
8. WHEN launch checklist is run THEN reduced motion behavior SHALL be checked.

## Requirement 12: SEO and discovery readiness

### User story

As an operator, I want public content discoverable while private content remains hidden.

### Acceptance criteria

1. WHEN launch checklist is run THEN public novel metadata SHALL be verified.
2. WHEN launch checklist is run THEN public chapter metadata SHALL be verified.
3. WHEN launch checklist is run THEN canonical URLs SHALL be verified.
4. WHEN launch checklist is run THEN Open Graph/Twitter metadata SHALL be verified.
5. WHEN launch checklist is run THEN robots.txt SHALL be verified.
6. WHEN launch checklist is run THEN sitemap.xml SHALL be verified.
7. WHEN unpublished/private/taken-down content exists THEN it SHALL be excluded from sitemap.
8. WHEN unavailable/taken-down pages exist THEN noindex behavior SHALL be verified.

## Requirement 13: Observability readiness

### User story

As an operator, I want launch monitoring in place before public traffic arrives.

### Acceptance criteria

1. WHEN launch checklist is run THEN structured logs SHALL be verified.
2. WHEN launch checklist is run THEN request IDs SHALL be verified.
3. WHEN launch checklist is run THEN liveness endpoint SHALL be verified.
4. WHEN launch checklist is run THEN readiness endpoint SHALL be verified.
5. WHEN launch checklist is run THEN admin health SHALL be verified.
6. WHEN launch checklist is run THEN metrics baseline SHALL be verified if enabled.
7. WHEN launch checklist is run THEN worker/scheduler status SHALL be verified.
8. WHEN launch checklist is run THEN backup status SHALL be visible.
9. WHEN launch checklist is run THEN frontend error logging SHALL be verified or intentionally disabled.

## Requirement 14: Backup and maintenance readiness

### User story

As an operator, I want backups and cleanup jobs ready before launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN scheduled backups SHALL be configured or exception recorded.
2. WHEN launch checklist is run THEN backup target reachability SHALL be verified.
3. WHEN launch checklist is run THEN backup retention SHALL be verified.
4. WHEN launch checklist is run THEN restore drill SHALL be completed or scheduled with accepted exception.
5. WHEN launch checklist is run THEN maintenance cron SHALL be configured.
6. WHEN launch checklist is run THEN temp/activity/cache/export cleanup SHALL be verified where applicable.
7. WHEN launch checklist is run THEN scheduler runtime persistence SHALL be verified.
8. WHEN backup readiness fails without accepted exception THEN launch SHALL be blocked.

## Requirement 15: Production deployment readiness

### User story

As an operator, I want production deployment hardening verified before launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN production config validation SHALL pass.
2. WHEN launch checklist is run THEN required secrets SHALL be configured.
3. WHEN launch checklist is run THEN debug mode SHALL be disabled.
4. WHEN launch checklist is run THEN secure cookies SHALL be verified.
5. WHEN launch checklist is run THEN CORS SHALL be restricted.
6. WHEN launch checklist is run THEN trusted proxy settings SHALL be verified.
7. WHEN launch checklist is run THEN security headers SHALL be present.
8. WHEN launch checklist is run THEN migrations SHALL be applied.
9. WHEN launch checklist is run THEN workers/schedulers SHALL be running safely.
10. WHEN launch checklist is run THEN storage public/private paths SHALL be verified.

## Requirement 16: Rollback and kill-switch readiness

### User story

As an operator, I want rollback and kill switches ready before launch.

### Acceptance criteria

1. WHEN launch checklist is run THEN app rollback procedure SHALL be documented.
2. WHEN launch checklist is run THEN migration rollback limitations SHALL be documented.
3. WHEN launch checklist is run THEN worker/scheduler pause procedure SHALL be documented.
4. WHEN launch checklist is run THEN public cache invalidation procedure SHALL be documented.
5. WHEN launch checklist is run THEN public reader disable procedure SHALL exist or exception recorded.
6. WHEN launch checklist is run THEN optional feature kill switches SHALL be documented.
7. WHEN launch checklist is run THEN rollback owner SHALL be assigned.
8. WHEN rollback path is missing THEN launch SHALL be blocked or explicitly waived.

## Requirement 17: Documentation readiness

### User story

As a maintainer/operator, I want launch-critical documentation complete.

### Acceptance criteria

1. WHEN launch checklist is run THEN getting-started/operator docs SHALL be current.
2. WHEN launch checklist is run THEN production environment documentation SHALL be current.
3. WHEN launch checklist is run THEN deployment steps SHALL be documented.
4. WHEN launch checklist is run THEN backup/restore docs SHALL be current.
5. WHEN launch checklist is run THEN admin operations docs SHALL be current.
6. WHEN launch checklist is run THEN takedown/legal operation docs SHALL be current.
7. WHEN launch checklist is run THEN troubleshooting docs SHALL include common launch failures.
8. WHEN critical docs are missing THEN launch SHALL be blocked or waived.

## Requirement 18: Known issues and accepted risks

### User story

As a launch approver, I want known issues documented so launch risk is explicit.

### Acceptance criteria

1. WHEN a known issue exists THEN it SHALL be listed.
2. WHEN a known issue affects launch safety THEN it SHALL be marked blocker unless waived.
3. WHEN a known issue is waived THEN waiver owner SHALL be recorded.
4. WHEN a known issue is waived THEN mitigation or follow-up SHALL be recorded.
5. WHEN accepted risk exists THEN launch approver SHALL acknowledge it.
6. WHEN blocker issues remain unwaived THEN launch decision SHALL be `NO-GO`.

## Requirement 19: Go/no-go decision

### User story

As a release owner, I want a formal go/no-go decision before public launch.

### Acceptance criteria

1. WHEN checklist is complete THEN final decision SHALL be recorded as `GO` or `NO-GO`.
2. WHEN decision is recorded THEN release version/commit SHALL be recorded.
3. WHEN decision is recorded THEN date/time SHALL be recorded.
4. WHEN decision is recorded THEN approver SHALL be recorded.
5. WHEN decision is `GO` THEN no unwaived blockers SHALL remain.
6. WHEN decision is `GO` THEN rollback owner SHALL be assigned.
7. WHEN decision is `GO` THEN monitoring owner SHALL be assigned.
8. WHEN decision is `NO-GO` THEN blockers and next actions SHALL be recorded.

## Requirement 20: Post-launch monitoring

### User story

As an operator, I want post-launch monitoring so issues are detected quickly.

### Acceptance criteria

1. WHEN launch starts THEN public reader errors SHALL be monitored.
2. WHEN launch starts THEN translation job failures SHALL be monitored.
3. WHEN launch starts THEN queue depth and worker health SHALL be monitored.
4. WHEN launch starts THEN database/storage errors SHALL be monitored.
5. WHEN launch starts THEN rate-limit/abuse spikes SHALL be monitored.
6. WHEN launch starts THEN backup failures SHALL be monitored.
7. WHEN launch starts THEN frontend errors SHALL be monitored where enabled.
8. WHEN launch starts THEN monitoring window and owner SHALL be recorded.
9. WHEN severe issue occurs THEN rollback/mitigation procedure SHALL be used.

## Requirement 21: Completion verification

### User story

As a maintainer, I want this spec complete only when launch readiness can be decided from evidence.

### Acceptance criteria

1. WHEN checklist is opened THEN all readiness categories SHALL be present.
2. WHEN each category is reviewed THEN status and evidence SHALL be recorded.
3. WHEN core product flow is run THEN result SHALL be recorded.
4. WHEN public reader safety checks are run THEN result SHALL be recorded.
5. WHEN production hardening checks are run THEN result SHALL be recorded.
6. WHEN backup/rollback checks are run THEN result SHALL be recorded.
7. WHEN blockers exist THEN launch decision SHALL be `NO-GO` unless waived.
8. WHEN final decision is `GO` THEN release version, approver, rollback owner, and monitoring owner SHALL be recorded.
