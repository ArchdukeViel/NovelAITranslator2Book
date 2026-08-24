# Launch Acceptance Requirements

## Goal

Produce a defensible `GO` or `NO-GO` decision from hosted evidence.

## Requirements

1. Use operator gates in `docs/WORK.md`; do not duplicate another checklist.
2. Evidence records candidate commit/version, environment, UTC time, operator,
   exact command or URL, sanitized result, blocker, and waiver where applicable.
3. Verify product flow, auth/security, legal propagation, accessibility,
   performance, SEO, monitoring/alerts, recovery, and rollback.
4. `GO` requires zero unwaived blockers and named launch/rollback/monitoring owners.
5. Never include secrets, private content, connection strings, raw paths, or traces.

Generated reader downloads are not applicable and require no acceptance work.
