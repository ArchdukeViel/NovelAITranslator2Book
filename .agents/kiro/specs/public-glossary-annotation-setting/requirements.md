# requirements.md

# Requirements: Public Glossary Annotations Setting

## Introduction

Public glossary annotations need a configurable control layer. Operators should be able to enable or disable annotations globally and optionally override the setting per novel. The public reader must respect the effective setting and return an empty annotations list when disabled.

## Requirement 1: Global setting

### User story

As an operator, I want a global public glossary annotation setting so I can enable or disable the feature across the whole site.

### Acceptance criteria

1. WHEN the global setting is disabled THEN public reader glossary annotations SHALL be disabled for all novels.
2. WHEN the global setting is enabled THEN public reader glossary annotations MAY be enabled according to per-novel settings.
3. WHEN the global setting is missing THEN the system SHALL use a safe configured default.
4. WHEN the global setting is disabled THEN the public chapter API SHALL return `glossary_annotations: []`.
5. WHEN the global setting is disabled THEN the public chapter API SHOULD avoid calling annotation lookup.
6. WHEN the global setting is updated THEN the new value SHALL apply to future public reader responses.
7. WHEN deployment-level config disables annotations THEN database/admin settings SHALL NOT override the kill switch.

## Requirement 2: Per-novel setting

### User story

As an admin, I want to control public glossary annotations per novel so I can roll the feature out title by title.

### Acceptance criteria

1. WHEN a novel setting is `inherit` THEN the novel SHALL follow the global setting.
2. WHEN a novel setting is `enabled` and global setting allows annotations THEN annotations SHALL be enabled for that novel.
3. WHEN a novel setting is `disabled` THEN annotations SHALL be disabled for that novel.
4. WHEN global setting is disabled THEN per-novel enabled SHALL NOT expose annotations.
5. WHEN no per-novel setting exists THEN the system SHALL treat it as `inherit`.
6. WHEN a per-novel setting is updated THEN the new value SHALL apply to future public reader responses for that novel.
7. WHEN an invalid per-novel mode is submitted THEN the system SHALL return a validation error.

## Requirement 3: Effective setting service

### User story

As a maintainer, I want one service to resolve annotation settings so public reader behavior is consistent.

### Acceptance criteria

1. WHEN code needs to know whether annotations are enabled THEN it SHALL use the effective setting service or equivalent shared helper.
2. WHEN global setting is disabled THEN effective setting SHALL return disabled.
3. WHEN global setting is enabled and novel mode is inherit THEN effective setting SHALL return enabled.
4. WHEN global setting is enabled and novel mode is enabled THEN effective setting SHALL return enabled.
5. WHEN global setting is enabled and novel mode is disabled THEN effective setting SHALL return disabled.
6. WHEN setting lookup fails in public reader context THEN effective setting SHALL fail closed and return disabled.
7. WHEN admin context requests effective setting THEN response SHOULD include a safe reason for the effective state.

## Requirement 4: Public chapter API behavior

### User story

As a reader, I want public chapters to load normally whether annotations are enabled or disabled.

### Acceptance criteria

1. WHEN annotations are effectively enabled THEN the public chapter API SHALL perform annotation lookup according to existing annotation wiring.
2. WHEN annotations are effectively disabled THEN the public chapter API SHALL return `glossary_annotations: []`.
3. WHEN annotations are effectively disabled THEN the public chapter API SHALL preserve all other chapter response fields.
4. WHEN annotations are effectively disabled THEN the public chapter API SHOULD avoid unnecessary annotation service calls.
5. WHEN annotation setting lookup fails THEN the public chapter API SHALL return `glossary_annotations: []`.
6. WHEN the chapter is unpublished or unavailable THEN existing public reader behavior SHALL remain unchanged.
7. WHEN annotations are enabled THEN glossary term approval and visibility rules SHALL still apply.
8. WHEN annotations are disabled THEN no private glossary metadata SHALL be exposed.

## Requirement 5: Admin global settings API

### User story

As an admin, I want to read and update the global annotation setting through an admin API.

### Acceptance criteria

1. WHEN an admin requests public reader settings THEN the API SHALL return the global annotation setting.
2. WHEN an admin updates the global annotation setting THEN the API SHALL persist the new value.
3. WHEN an unauthenticated user requests or updates the setting THEN the API SHALL return `401 Unauthorized`.
4. WHEN a non-admin requests or updates the setting THEN the API SHALL return `403 Forbidden`.
5. WHEN deployment-level config disables annotations THEN the API response SHALL indicate that annotations are blocked by deployment config.
6. WHEN an invalid payload is submitted THEN the API SHALL return a validation error.
7. WHEN the setting is updated THEN related caches SHALL be invalidated or versioned.
8. WHEN the setting is updated THEN an admin audit event SHALL be recorded.

## Requirement 6: Admin per-novel settings API

### User story

As an admin, I want to read and update per-novel annotation settings through an admin API.

### Acceptance criteria

1. WHEN an admin requests a novel’s public reader settings THEN the API SHALL return the novel annotation mode.
2. WHEN an admin requests a novel’s public reader settings THEN the API SHALL return effective annotation state.
3. WHEN an admin updates a novel annotation mode THEN the API SHALL persist the new mode.
4. WHEN an invalid mode is submitted THEN the API SHALL return a validation error.
5. WHEN a novel does not exist THEN the API SHALL return not found.
6. WHEN an unauthenticated user requests or updates novel settings THEN the API SHALL return `401 Unauthorized`.
7. WHEN a non-admin requests or updates novel settings THEN the API SHALL return `403 Forbidden`.
8. WHEN a novel setting is updated THEN affected public reader caches SHALL be invalidated or versioned.
9. WHEN a novel setting is updated THEN an admin audit event SHALL be recorded.

## Requirement 7: Admin UI controls

### User story

As an admin, I want UI controls for annotation settings so I can manage the feature without editing configuration manually.

### Acceptance criteria

1. WHEN an admin opens public reader settings THEN the UI SHALL show the global glossary annotation setting.
2. WHEN an admin changes the global setting THEN the UI SHALL save it through the admin API.
3. WHEN an admin opens a novel settings page THEN the UI SHOULD show per-novel annotation mode.
4. WHEN an admin changes per-novel mode THEN the UI SHALL save it through the admin API.
5. WHEN deployment config disables annotations THEN the UI SHALL show that global admin controls cannot override it.
6. WHEN settings load fails THEN the UI SHALL show a safe error.
7. WHEN settings update fails THEN the UI SHALL show a safe error and preserve or restore previous state.
8. WHEN settings update succeeds THEN the UI SHALL show success or updated effective state.

## Requirement 8: Cache compatibility

### User story

As an operator, I want setting changes to avoid stale cached reader responses that still include annotations.

### Acceptance criteria

1. WHEN global annotation setting changes THEN public reader cache SHALL be invalidated or versioned.
2. WHEN per-novel annotation setting changes THEN affected novel reader cache SHALL be invalidated or versioned.
3. WHEN public chapter responses include annotations and are cached THEN cache keys SHALL account for effective annotation setting or be invalidated on change.
4. WHEN annotations are disabled after previously being enabled THEN cached responses SHALL NOT continue serving annotations.
5. WHEN cache invalidation fails THEN the system SHALL log a safe warning or fail the settings update according to project consistency policy.
6. WHEN no public reader cache exists THEN cache invalidation may be a no-op.
7. WHEN tests run THEN they SHALL cover that disabled settings do not serve stale annotations from cache where practical.

## Requirement 9: Audit logging

### User story

As an operator, I want annotation setting changes audited because they affect public data exposure.

### Acceptance criteria

1. WHEN global annotation setting changes THEN the system SHALL record an admin audit event.
2. WHEN per-novel annotation setting changes THEN the system SHALL record an admin audit event.
3. WHEN audit event is recorded THEN it SHALL include admin user, previous value, new value, and timestamp.
4. WHEN per-novel setting changes THEN audit event SHALL include novel ID.
5. WHEN audit logging fails THEN the system SHALL follow existing admin-action audit failure policy.
6. WHEN audit logs are stored THEN they SHALL not include glossary definitions, chapter text, prompts, or secrets.

## Requirement 10: Security and privacy

### User story

As an operator, I want annotation settings to control exposure safely and never bypass glossary visibility rules.

### Acceptance criteria

1. WHEN annotations are enabled by settings THEN unapproved glossary terms SHALL still not be exposed.
2. WHEN annotations are enabled by settings THEN private/internal terms SHALL still not be exposed.
3. WHEN annotations are enabled by settings THEN inactive aliases SHALL still not be exposed.
4. WHEN annotations are disabled by settings THEN no glossary annotation data SHALL be exposed.
5. WHEN setting lookup fails in public reader context THEN annotations SHALL fail closed.
6. WHEN public responses are returned THEN they SHALL not expose admin-only setting reasons unless explicitly safe.
7. WHEN settings APIs are called THEN only admins SHALL be able to update settings.
8. WHEN settings are logged or audited THEN secrets and private glossary content SHALL not be included.

## Requirement 11: Migration and defaults

### User story

As a maintainer, I want safe defaults and migration behavior so existing novels do not break.

### Acceptance criteria

1. WHEN the migration runs THEN existing novels SHALL receive default per-novel mode of `inherit` or equivalent.
2. WHEN the global setting is first introduced THEN it SHALL use a safe default according to environment/rollout policy.
3. WHEN old novels lack explicit setting rows or fields THEN effective setting resolution SHALL treat them as inherit.
4. WHEN the migration is rolled forward THEN public reader responses SHALL remain valid.
5. WHEN the setting field is nullable for inherit behavior THEN validation SHALL distinguish null/inherit from true/false modes.
6. WHEN tests run THEN migration/default behavior SHALL be covered.

## Requirement 12: Test coverage

### User story

As a maintainer, I want tests for annotation settings so public exposure controls do not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover global enabled behavior.
2. WHEN tests run THEN they SHALL cover global disabled behavior.
3. WHEN tests run THEN they SHALL cover per-novel inherit behavior.
4. WHEN tests run THEN they SHALL cover per-novel enabled behavior.
5. WHEN tests run THEN they SHALL cover per-novel disabled behavior.
6. WHEN tests run THEN they SHALL cover global kill switch overriding per-novel enabled.
7. WHEN tests run THEN they SHALL verify public reader returns empty annotations when disabled.
8. WHEN tests run THEN they SHALL verify annotation service is not called when disabled.
9. WHEN tests run THEN they SHALL verify annotation service is called when enabled.
10. WHEN tests run THEN they SHALL cover admin settings API authorization.
11. WHEN tests run THEN they SHALL cover invalid setting payloads.
12. WHEN tests run THEN they SHALL cover cache invalidation/versioning.
13. WHEN tests run THEN they SHALL cover audit log creation.
14. WHEN admin UI is implemented THEN tests SHALL cover controls, save success, and error states.

## Requirement 13: Completion verification

### User story

As an operator, I want a clear verification path so settings are only complete when public annotation exposure can be controlled safely.

### Acceptance criteria

1. WHEN global setting is disabled THEN a public chapter with matching glossary terms SHALL return `glossary_annotations: []`.
2. WHEN global setting is enabled and novel mode is inherit THEN a public chapter with matching glossary terms SHALL return annotations.
3. WHEN novel mode is disabled THEN a public chapter with matching glossary terms SHALL return `glossary_annotations: []`.
4. WHEN novel mode is enabled but global setting is disabled THEN the public chapter SHALL return `glossary_annotations: []`.
5. WHEN setting lookup fails in a controlled test THEN the public chapter SHALL return `glossary_annotations: []`.
6. WHEN admin changes settings THEN public reader cache SHALL not continue serving stale annotation data.
7. WHEN admin changes settings THEN audit log SHALL record the change.
8. WHEN non-admin attempts to change settings THEN access SHALL be blocked.
