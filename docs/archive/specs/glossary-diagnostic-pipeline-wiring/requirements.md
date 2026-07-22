# requirements.md

# Requirements: Glossary Diagnostics Pipeline Wiring

## Introduction

The translation pipeline needs glossary diagnostics wired into `TranslateStage` and persisted into activity metadata. This allows operators and maintainers to understand glossary coverage, conflicts, missed terms, and translation-quality risks without changing core translation behavior.

## Requirement 1: Normalize glossary diagnostics

### User story

As a maintainer, I want raw glossary diagnostic data normalized so downstream pipeline code receives a stable shape.

### Acceptance criteria

1. WHEN raw glossary diagnostics are available THEN the system SHALL normalize them with `normalize_glossary_diagnostics()`.
2. WHEN raw glossary diagnostics are missing THEN the system SHALL return an empty normalized diagnostic object.
3. WHEN raw glossary diagnostics contain unknown fields THEN the system SHALL ignore or safely preserve only allowed metadata.
4. WHEN raw glossary diagnostics contain invalid counts THEN the system SHALL coerce, omit, or safely default them.
5. WHEN raw glossary diagnostics contain unknown warning codes THEN the system SHALL normalize them to `unknown` or equivalent.
6. WHEN raw glossary diagnostics contain unknown severity values THEN the system SHALL normalize them to a safe default.
7. WHEN raw glossary diagnostics contain malformed term events THEN the system SHALL omit or safely normalize those events.
8. WHEN normalization succeeds THEN the result SHALL follow the configured normalized diagnostics schema.
9. WHEN normalization fails unexpectedly THEN the system SHALL return safe fallback diagnostics instead of crashing translation.

## Requirement 2: Diagnostic schema stability

### User story

As a developer, I want a stable glossary diagnostic schema so tests and activity metadata can rely on predictable fields.

### Acceptance criteria

1. WHEN normalized diagnostics are produced THEN they SHALL include a summary object.
2. WHEN normalized diagnostics are produced THEN they SHALL include a warnings list.
3. WHEN normalized diagnostics are produced THEN they SHOULD include term events when available and within configured limits.
4. WHEN normalized diagnostics are produced THEN they SHALL include a schema version.
5. WHEN warning entries are produced THEN they SHALL include code, severity, and safe message.
6. WHEN term event entries are produced THEN they SHALL include event type and available safe term identifiers.
7. WHEN source terms are included THEN they SHALL be bounded and safe.
8. WHEN diagnostics are serialized THEN they SHALL be JSON-compatible.
9. WHEN diagnostics are persisted THEN they SHALL not include raw prompts, full source text, full translated text, API keys, or secrets.

## Requirement 3: TranslateStage integration

### User story

As a maintainer, I want `TranslateStage` to attach normalized glossary diagnostics to translation results so the pipeline can aggregate them.

### Acceptance criteria

1. WHEN `TranslateStage` receives or produces raw glossary diagnostics THEN it SHALL call `normalize_glossary_diagnostics()`.
2. WHEN `TranslateStage` completes successfully THEN its result SHALL include normalized glossary diagnostics where the result shape supports metadata.
3. WHEN no glossary is used THEN `TranslateStage` SHALL include empty diagnostics or omit diagnostics according to the normalized contract.
4. WHEN diagnostic normalization fails THEN `TranslateStage` SHALL preserve the translation result and attach a safe malformed-diagnostics warning when practical.
5. WHEN translation itself fails THEN diagnostic handling SHALL not mask the original translation failure.
6. WHEN existing consumers read `TranslateStage` output THEN the diagnostic addition SHALL not break existing fields.
7. WHEN tests mock the normalizer THEN tests SHALL be able to verify that `TranslateStage` invokes it.

## Requirement 4: Glossary diagnostic aggregation

### User story

As an operator, I want diagnostics aggregated across chapters or batches so an activity shows useful summary information.

### Acceptance criteria

1. WHEN multiple chapter diagnostics exist THEN the system SHALL aggregate summary counters.
2. WHEN warnings exist across chapters THEN the system SHALL count warning codes.
3. WHEN conflicts exist across chapters THEN the system SHALL count conflicts.
4. WHEN term matches exist across chapters THEN the system SHALL count matched and applied terms.
5. WHEN chapter-level diagnostics exist THEN the system SHALL produce bounded chapter summaries.
6. WHEN diagnostic details exceed configured limits THEN the system SHALL truncate details.
7. WHEN truncation occurs THEN the system SHALL record that diagnostics were truncated.
8. WHEN aggregation receives malformed diagnostics THEN it SHALL skip or safely normalize them without failing the whole translation activity.
9. WHEN aggregation completes THEN the output SHALL be suitable for activity metadata.

## Requirement 5: Activity metadata persistence

### User story

As an operator, I want glossary diagnostics persisted in activity metadata so activity detail/status can show translation quality signals.

### Acceptance criteria

1. WHEN a translation activity produces glossary diagnostics THEN the system SHALL persist them under `metadata.glossary_diagnostics`.
2. WHEN activity metadata already contains other fields THEN glossary diagnostic persistence SHALL preserve existing metadata.
3. WHEN activity progress metadata exists THEN glossary diagnostic persistence SHALL not overwrite progress metadata.
4. WHEN crawl result metadata exists THEN glossary diagnostic persistence SHALL not overwrite crawl result metadata.
5. WHEN translation completes successfully THEN final aggregated glossary diagnostics SHALL be persisted.
6. WHEN translation fails after partial diagnostics are available THEN the system SHOULD persist partial diagnostics if safe.
7. WHEN metadata persistence fails THEN the system SHALL log a safe warning.
8. WHEN metadata persistence fails after translation succeeds THEN it SHALL not corrupt the translated output.
9. WHEN activity metadata is returned through existing APIs THEN glossary diagnostics SHALL be included if metadata is already exposed or whitelisted.

## Requirement 6: Metadata size bounds

### User story

As an operator, I want diagnostic metadata to stay bounded so activities do not store unbounded term-level data.

### Acceptance criteria

1. WHEN warning lists exceed configured limit THEN the system SHALL truncate warning details.
2. WHEN term event lists exceed configured limit THEN the system SHALL truncate term event details.
3. WHEN chapter summaries exceed configured limit THEN the system SHALL truncate chapter summaries.
4. WHEN serialized diagnostics exceed configured metadata size limit THEN the system SHALL reduce detail and keep summary fields.
5. WHEN diagnostics are truncated THEN metadata SHALL include `truncated` or equivalent.
6. WHEN details are truncated THEN summary counters SHALL still reflect the full known counts where practical.
7. WHEN truncation occurs THEN the system SHALL not fail translation solely because diagnostics were too large.

## Requirement 7: Error resilience

### User story

As a user, I want translations to continue even when diagnostic collection has problems.

### Acceptance criteria

1. WHEN glossary diagnostics are missing THEN translation SHALL continue.
2. WHEN raw diagnostics are malformed THEN translation SHALL continue.
3. WHEN normalization throws unexpectedly THEN translation SHALL continue if translation itself succeeded.
4. WHEN aggregation throws unexpectedly THEN translation SHALL continue if translation itself succeeded.
5. WHEN metadata persistence fails THEN translation SHALL continue if translation itself succeeded.
6. WHEN translation fails independently THEN diagnostic handling SHALL not hide the translation failure.
7. WHEN diagnostic errors occur THEN the system SHALL log safe warnings.
8. WHEN diagnostic errors are attached to metadata THEN they SHALL use safe warning codes.

## Requirement 8: Security and privacy

### User story

As a maintainer, I want glossary diagnostics to avoid leaking sensitive prompts, provider data, or private text.

### Acceptance criteria

1. WHEN diagnostics are normalized THEN they SHALL not include provider API keys.
2. WHEN diagnostics are normalized THEN they SHALL not include raw provider requests or responses.
3. WHEN diagnostics are normalized THEN they SHALL not include full source chapter text.
4. WHEN diagnostics are normalized THEN they SHALL not include full translated chapter text.
5. WHEN warning messages are stored THEN they SHALL be bounded and redacted.
6. WHEN term strings are stored THEN they SHALL be bounded by configured length.
7. WHEN diagnostics are exposed through activity APIs THEN existing activity authorization SHALL apply.
8. WHEN diagnostics are logged THEN logs SHALL use safe summaries, not full diagnostic payloads.

## Requirement 9: Activity response compatibility

### User story

As a frontend or API consumer, I want glossary diagnostics available through existing activity responses without breaking current response shape.

### Acceptance criteria

1. WHEN activity metadata is already exposed THEN `metadata.glossary_diagnostics` SHALL be included after persistence.
2. WHEN activity response models whitelist metadata keys THEN they SHALL be updated to allow `glossary_diagnostics`.
3. WHEN old activities do not have glossary diagnostics THEN API responses SHALL remain valid.
4. WHEN glossary diagnostics are present THEN API responses SHALL serialize them as JSON-compatible metadata.
5. WHEN diagnostics are omitted due to permissions or response shape THEN the omission SHALL not break activity status responses.
6. WHEN existing frontend consumers parse activity metadata THEN the new field SHALL be additive.

## Requirement 10: Observability

### User story

As an operator, I want safe logs around diagnostic wiring so I can troubleshoot missing or malformed diagnostics.

### Acceptance criteria

1. WHEN diagnostics are normalized THEN the system SHOULD log a safe debug/info event.
2. WHEN diagnostics are malformed THEN the system SHALL log a safe warning.
3. WHEN diagnostics are aggregated THEN the system SHOULD log summary counts.
4. WHEN diagnostics are persisted THEN the system SHOULD log a safe persistence event.
5. WHEN metadata persistence fails THEN the system SHALL log a safe warning.
6. WHEN logs are emitted THEN they SHALL include activity ID and chapter ID where available.
7. WHEN logs are emitted THEN they SHALL not include secrets, raw prompts, full source text, or full translated text.

## Requirement 11: Test coverage

### User story

As a maintainer, I want tests for diagnostic wiring so future translation changes do not silently drop glossary diagnostics.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover normalizer empty input.
2. WHEN tests run THEN they SHALL cover normalizer valid input.
3. WHEN tests run THEN they SHALL cover normalizer malformed input.
4. WHEN tests run THEN they SHALL cover warning code normalization.
5. WHEN tests run THEN they SHALL cover severity normalization.
6. WHEN tests run THEN they SHALL cover term event normalization.
7. WHEN tests run THEN they SHALL verify `TranslateStage` calls the normalizer.
8. WHEN tests run THEN they SHALL verify translation output is preserved when diagnostics fail.
9. WHEN tests run THEN they SHALL cover aggregation across multiple chapters.
10. WHEN tests run THEN they SHALL cover metadata truncation.
11. WHEN tests run THEN they SHALL cover activity metadata merge/persistence.
12. WHEN tests run THEN they SHALL cover partial diagnostics on failure where implemented.
13. WHEN tests run THEN they SHALL cover API response compatibility if response models are updated.
14. WHEN tests run THEN they SHALL cover redaction/security rules where practical.

## Requirement 12: Completion verification

### User story

As a maintainer, I want a clear completion check so this technical debt is not considered done until diagnostics are visible in activity metadata.

### Acceptance criteria

1. WHEN a translation activity uses glossary terms THEN activity metadata SHALL include glossary diagnostics.
2. WHEN glossary terms conflict or produce warnings THEN activity metadata SHALL include warning summaries.
3. WHEN glossary diagnostics are malformed in a test path THEN translation SHALL still complete.
4. WHEN multiple chapters are translated THEN activity metadata SHALL include aggregated diagnostics.
5. WHEN metadata is inspected through activity API THEN diagnostics SHALL be visible to authorized users.
6. WHEN diagnostics exceed limits THEN metadata SHALL be bounded and marked truncated.
7. WHEN existing translation tests run THEN they SHALL continue passing.
