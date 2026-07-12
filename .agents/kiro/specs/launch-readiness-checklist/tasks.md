# tasks.md

# Tasks: Launch Readiness Checklist

## Task List

* [ ] 0. Create launch readiness artifact

  * [ ] 0.1 Create `docs/operations/launch-checklist.md` or equivalent operator checklist. (REQ-1)
  * [ ] 0.2 Add status field for each checklist item. (REQ-1, REQ-2)
  * [ ] 0.3 Add owner field for each category or item. (REQ-1)
  * [ ] 0.4 Add evidence/notes field. (REQ-1)
  * [ ] 0.5 Add blocker field. (REQ-1, REQ-18)
  * [ ] 0.6 Add waiver field. (REQ-2, REQ-18)
  * [ ] 0.7 Add final go/no-go section. (REQ-19)
  * [ ] 0.8 Add post-launch monitoring section. (REQ-20)

* [ ] 1. Define launch scope

  * [ ] 1.1 Define which features are in launch scope. (REQ-1)
  * [ ] 1.2 Define which optional specs/features are out of scope. (REQ-2)
  * [ ] 1.3 Mark out-of-scope checks as `not_applicable`. (REQ-2)
  * [ ] 1.4 Assign launch owner. (REQ-19)
  * [ ] 1.5 Assign rollback owner. (REQ-16, REQ-19)
  * [ ] 1.6 Assign monitoring owner. (REQ-20)
  * [ ] 1.7 Record target release version/commit. (REQ-19)

* [ ] 2. Verify core product flows

  * [ ] 2.1 Create/import a test novel. (REQ-3)
  * [ ] 2.2 Crawl/fetch chapters. (REQ-3)
  * [ ] 2.3 Scrape chapter content. (REQ-3)
  * [ ] 2.4 Run translation job. (REQ-3)
  * [ ] 2.5 Verify translated chapter persistence. (REQ-3)
  * [ ] 2.6 Verify activity/progress visibility. (REQ-3)
  * [ ] 2.7 Publish content. (REQ-3)
  * [ ] 2.8 View public novel and chapter. (REQ-3)
  * [ ] 2.9 Generate/export artifact. (REQ-3, REQ-6)
  * [ ] 2.10 Record evidence and blockers. (REQ-1, REQ-3)

* [ ] 3. Verify translation and glossary readiness

  * [ ] 3.1 Verify JP→EN prompt policy is current. (REQ-4)
  * [ ] 3.2 Run translation prompt tests/snapshots if available. (REQ-4)
  * [ ] 3.3 Verify glossary terms are injected where expected. (REQ-4)
  * [ ] 3.4 Verify glossary diagnostics persistence. (REQ-4)
  * [ ] 3.5 Verify public-safe glossary annotations. (REQ-4)
  * [ ] 3.6 Verify global annotation setting. (REQ-4)
  * [ ] 3.7 Verify per-novel annotation setting. (REQ-4)
  * [ ] 3.8 Verify glossary revision invalidation if implemented. (REQ-4)
  * [ ] 3.9 Verify translation failure safe error handling. (REQ-4)
  * [ ] 3.10 Record evidence and blockers. (REQ-1, REQ-4)

* [ ] 4. Verify public reader readiness

  * [ ] 4.1 Verify published public novel page loads. (REQ-5)
  * [ ] 4.2 Verify published public chapter page loads. (REQ-5)
  * [ ] 4.3 Verify unpublished content is blocked. (REQ-5)
  * [ ] 4.4 Verify private content is blocked. (REQ-5)
  * [ ] 4.5 Verify taken-down content is blocked. (REQ-5, REQ-9)
  * [ ] 4.6 Verify graceful degradation/fallback behavior. (REQ-5)
  * [ ] 4.7 Verify reader loading/error/empty states. (REQ-5)
  * [ ] 4.8 Verify glossary annotations render only when enabled. (REQ-5)
  * [ ] 4.9 Verify public reader cache respects publication/takedown state. (REQ-5)
  * [ ] 4.10 Record evidence and blockers. (REQ-1, REQ-5)

* [ ] 5. Verify export readiness

  * [ ] 5.1 Verify PDF exporter is registered. (REQ-6)
  * [ ] 5.2 Generate export artifact. (REQ-6)
  * [ ] 5.3 Verify export manifest is recorded. (REQ-6)
  * [ ] 5.4 Verify export freshness status if implemented. (REQ-6)
  * [ ] 5.5 Verify stale/missing export states. (REQ-6)
  * [ ] 5.6 Verify admin export manifest UI. (REQ-6)
  * [ ] 5.7 Verify public download does not expose private paths/signed URLs unsafely. (REQ-6)
  * [ ] 5.8 Verify taken-down content cannot be downloaded publicly. (REQ-6, REQ-9)
  * [ ] 5.9 Record evidence and blockers. (REQ-1, REQ-6)

* [ ] 6. Verify admin operations readiness

  * [ ] 6.1 Verify admin user management. (REQ-7)
  * [ ] 6.2 Verify admin audit log viewer. (REQ-7)
  * [ ] 6.3 Verify admin health page. (REQ-7)
  * [ ] 6.4 Verify metrics dashboard if enabled. (REQ-7, REQ-13)
  * [ ] 6.5 Verify analytics dashboard if enabled. (REQ-7)
  * [ ] 6.6 Verify backup/status page if enabled. (REQ-7, REQ-14)
  * [ ] 6.7 Verify maintenance status if enabled. (REQ-7, REQ-14)
  * [ ] 6.8 Verify takedown admin workflow. (REQ-7, REQ-9)
  * [ ] 6.9 Verify non-admin users cannot access admin routes. (REQ-7, REQ-8)
  * [ ] 6.10 Record evidence and blockers. (REQ-1, REQ-7)

* [ ] 7. Verify security and privacy readiness

  * [ ] 7.1 Verify auth required for protected routes. (REQ-8)
  * [ ] 7.2 Verify admin authorization. (REQ-8)
  * [ ] 7.3 Verify session revocation. (REQ-8)
  * [ ] 7.4 Verify disabled user access is blocked. (REQ-8)
  * [ ] 7.5 Verify production CORS/CSRF safety. (REQ-8, REQ-15)
  * [ ] 7.6 Verify rate limits. (REQ-8)
  * [ ] 7.7 Verify secrets are not exposed in frontend/config/logs. (REQ-8)
  * [ ] 7.8 Verify logs redact sensitive data. (REQ-8)
  * [ ] 7.9 Verify analytics does not store raw private content. (REQ-8)
  * [ ] 7.10 Verify audit logs redact unsafe fields. (REQ-8)
  * [ ] 7.11 Verify public APIs do not expose admin/private fields. (REQ-8)
  * [ ] 7.12 Record evidence and blockers. (REQ-1, REQ-8)

* [ ] 8. Verify legal/takedown readiness

  * [ ] 8.1 Submit public takedown request if intake is enabled. (REQ-9)
  * [ ] 8.2 Verify admin can review request. (REQ-9)
  * [ ] 8.3 Apply takedown to test public content. (REQ-9)
  * [ ] 8.4 Verify public reader does not serve taken-down content. (REQ-9)
  * [ ] 8.5 Verify sitemap excludes taken-down content. (REQ-9, REQ-12)
  * [ ] 8.6 Verify SEO noindex/unavailable behavior. (REQ-9, REQ-12)
  * [ ] 8.7 Verify export/download blocked for taken-down content. (REQ-9)
  * [ ] 8.8 Verify takedown audit events. (REQ-9)
  * [ ] 8.9 Verify private legal details are not public. (REQ-9)
  * [ ] 8.10 Record evidence and blockers. (REQ-1, REQ-9)

* [ ] 9. Verify performance readiness

  * [ ] 9.1 Verify public reader request count. (REQ-10)
  * [ ] 9.2 Inspect public reader bundle budget/report. (REQ-10)
  * [ ] 9.3 Render long chapter fixture. (REQ-10)
  * [ ] 9.4 Render many-annotation fixture if annotations are enabled. (REQ-10)
  * [ ] 9.5 Verify cover image optimization. (REQ-10)
  * [ ] 9.6 Verify public cache improves repeat requests where configured. (REQ-10)
  * [ ] 9.7 Record performance exceptions or blockers. (REQ-10, REQ-18)
  * [ ] 9.8 Record evidence. (REQ-1, REQ-10)

* [ ] 10. Verify accessibility readiness

  * [ ] 10.1 Run keyboard-only public reader flow. (REQ-11)
  * [ ] 10.2 Verify skip links. (REQ-11)
  * [ ] 10.3 Verify reader settings keyboard operation. (REQ-11)
  * [ ] 10.4 Verify chapter navigation keyboard operation. (REQ-11)
  * [ ] 10.5 Verify glossary annotation keyboard access if enabled. (REQ-11)
  * [ ] 10.6 Verify headings and landmarks. (REQ-11)
  * [ ] 10.7 Check 200% zoom. (REQ-11)
  * [ ] 10.8 Check reduced motion. (REQ-11)
  * [ ] 10.9 Record evidence and blockers. (REQ-1, REQ-11)

* [ ] 11. Verify SEO and discovery readiness

  * [ ] 11.1 Inspect public novel metadata. (REQ-12)
  * [ ] 11.2 Inspect public chapter metadata. (REQ-12)
  * [ ] 11.3 Verify canonical URLs. (REQ-12)
  * [ ] 11.4 Verify Open Graph/Twitter metadata. (REQ-12)
  * [ ] 11.5 Request robots.txt. (REQ-12)
  * [ ] 11.6 Request sitemap.xml. (REQ-12)
  * [ ] 11.7 Verify unpublished/private/taken-down content is excluded from sitemap. (REQ-12)
  * [ ] 11.8 Verify noindex for unavailable/taken-down pages. (REQ-12)
  * [ ] 11.9 Record evidence and blockers. (REQ-1, REQ-12)

* [ ] 12. Verify observability readiness

  * [ ] 12.1 Verify structured logs. (REQ-13)
  * [ ] 12.2 Verify request IDs. (REQ-13)
  * [ ] 12.3 Verify `/health/live`. (REQ-13)
  * [ ] 12.4 Verify `/health/ready`. (REQ-13)
  * [ ] 12.5 Verify admin health. (REQ-13)
  * [ ] 12.6 Verify metrics baseline if enabled. (REQ-13)
  * [ ] 12.7 Verify worker/scheduler status. (REQ-13)
  * [ ] 12.8 Verify backup status visibility. (REQ-13, REQ-14)
  * [ ] 12.9 Verify frontend error logging or intentional no-op. (REQ-13)
  * [ ] 12.10 Record evidence and blockers. (REQ-1, REQ-13)

* [ ] 13. Verify backup and maintenance readiness

  * [ ] 13.1 Verify scheduled backup config. (REQ-14)
  * [ ] 13.2 Verify backup target reachability. (REQ-14)
  * [ ] 13.3 Verify backup retention. (REQ-14)
  * [ ] 13.4 Complete restore drill or record accepted exception. (REQ-14, REQ-18)
  * [ ] 13.5 Verify maintenance cron config. (REQ-14)
  * [ ] 13.6 Verify cleanup of temp/activity/cache/export data where applicable. (REQ-14)
  * [ ] 13.7 Verify scheduler runtime state persistence. (REQ-14)
  * [ ] 13.8 Record evidence and blockers. (REQ-1, REQ-14)

* [ ] 14. Verify production deployment readiness

  * [ ] 14.1 Run production config validation. (REQ-15)
  * [ ] 14.2 Verify required secrets configured. (REQ-15)
  * [ ] 14.3 Verify debug mode disabled. (REQ-15)
  * [ ] 14.4 Verify secure cookies. (REQ-15)
  * [ ] 14.5 Verify restricted CORS. (REQ-15)
  * [ ] 14.6 Verify trusted proxy settings. (REQ-15)
  * [ ] 14.7 Verify security headers. (REQ-15)
  * [ ] 14.8 Verify migrations applied. (REQ-15)
  * [ ] 14.9 Verify workers/schedulers running safely. (REQ-15)
  * [ ] 14.10 Verify storage public/private paths. (REQ-15)
  * [ ] 14.11 Record evidence and blockers. (REQ-1, REQ-15)

* [ ] 15. Verify rollback and kill-switch readiness

  * [ ] 15.1 Verify app rollback procedure. (REQ-16)
  * [ ] 15.2 Verify migration rollback notes. (REQ-16)
  * [ ] 15.3 Verify worker/scheduler pause procedure. (REQ-16)
  * [ ] 15.4 Verify public cache invalidation procedure. (REQ-16)
  * [ ] 15.5 Verify public reader disable procedure or accepted exception. (REQ-16)
  * [ ] 15.6 Verify optional feature kill switches. (REQ-16)
  * [ ] 15.7 Assign rollback owner. (REQ-16, REQ-19)
  * [ ] 15.8 Record evidence and blockers. (REQ-1, REQ-16)

* [ ] 16. Verify documentation readiness

  * [ ] 16.1 Verify getting-started/operator docs. (REQ-17)
  * [ ] 16.2 Verify production environment docs. (REQ-17)
  * [ ] 16.3 Verify deployment docs. (REQ-17)
  * [ ] 16.4 Verify backup/restore docs. (REQ-17)
  * [ ] 16.5 Verify admin operations docs. (REQ-17)
  * [ ] 16.6 Verify takedown/legal operations docs. (REQ-17)
  * [ ] 16.7 Verify troubleshooting docs. (REQ-17)
  * [ ] 16.8 Record evidence and blockers. (REQ-1, REQ-17)

* [ ] 17. Record known issues and accepted risks

  * [ ] 17.1 List known issues. (REQ-18)
  * [ ] 17.2 Mark launch blockers. (REQ-18)
  * [ ] 17.3 Record waivers with owner and reason. (REQ-18)
  * [ ] 17.4 Record mitigation/follow-up for each waived risk. (REQ-18)
  * [ ] 17.5 Verify no unwaived blockers remain before GO decision. (REQ-18, REQ-19)

* [ ] 18. Hold go/no-go review

  * [ ] 18.1 Review all checklist categories. (REQ-19)
  * [ ] 18.2 Verify release version/commit. (REQ-19)
  * [ ] 18.3 Verify approver. (REQ-19)
  * [ ] 18.4 Verify rollback owner. (REQ-19)
  * [ ] 18.5 Verify monitoring owner. (REQ-19, REQ-20)
  * [ ] 18.6 Record `GO` only if no unwaived blockers remain. (REQ-19)
  * [ ] 18.7 Record `NO-GO` with blockers and next actions if not ready. (REQ-19)

* [ ] 19. Prepare post-launch monitoring

  * [ ] 19.1 Define first 2-hour monitoring plan. (REQ-20)
  * [ ] 19.2 Define first 24-hour monitoring plan. (REQ-20)
  * [ ] 19.3 Define first 7-day monitoring plan. (REQ-20)
  * [ ] 19.4 Monitor public reader errors. (REQ-20)
  * [ ] 19.5 Monitor translation failures. (REQ-20)
  * [ ] 19.6 Monitor queue depth and worker health. (REQ-20)
  * [ ] 19.7 Monitor database/storage errors. (REQ-20)
  * [ ] 19.8 Monitor rate-limit/abuse spikes. (REQ-20)
  * [ ] 19.9 Monitor backup failures. (REQ-20)
  * [ ] 19.10 Monitor frontend errors where enabled. (REQ-20)

* [ ] 20. Completion verification

  * [ ] 20.1 Open launch checklist and verify all categories are present. (REQ-21)
  * [ ] 20.2 Verify every category has status and evidence. (REQ-21)
  * [ ] 20.3 Verify core product flow result is recorded. (REQ-21)
  * [ ] 20.4 Verify public reader safety checks are recorded. (REQ-21)
  * [ ] 20.5 Verify production hardening checks are recorded. (REQ-21)
  * [ ] 20.6 Verify backup/rollback checks are recorded. (REQ-21)
  * [ ] 20.7 Verify blocker/waiver list is complete. (REQ-18, REQ-21)
  * [ ] 20.8 Verify final decision is recorded. (REQ-19, REQ-21)
  * [ ] 20.9 If decision is `GO`, verify release version, approver, rollback owner, and monitoring owner are recorded. (REQ-19, REQ-21)
  * [ ] 20.10 Mark `launch-readiness-checklist` complete only after launch readiness can be decided from recorded evidence.
