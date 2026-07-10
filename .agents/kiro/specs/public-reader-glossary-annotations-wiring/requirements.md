# requirements.md

# Requirements: Public Reader Glossary Annotations Wiring

## Introduction

The public reader chapter API needs to expose glossary annotations produced by `PublicGlossaryAnnotationsService.find_annotations()`. The response must include a new additive `glossary_annotations` field while preserving existing public reader behavior and preventing private or unapproved glossary data from leaking.

## Requirement 1: Public chapter response field

### User story

As a frontend developer, I want public chapter responses to include glossary annotations so the reader UI can later render highlights and tooltips.

### Acceptance criteria

1. WHEN a public chapter response is returned THEN it SHALL include `glossary_annotations`.
2. WHEN no annotations are available THEN `glossary_annotations` SHALL be an empty list.
3. WHEN annotations are available THEN `glossary_annotations` SHALL contain public-safe annotation objects.
4. WHEN old clients ignore the new field THEN existing reader behavior SHALL remain unchanged.
5. WHEN the response model is generated or validated THEN `glossary_annotations` SHALL be included in the public chapter response schema.
6. WHEN a chapter is unavailable or unpublished THEN the API SHALL preserve existing not-found or unavailable behavior and SHALL NOT expose annotations.

## Requirement 2: Service wiring

### User story

As a maintainer, I want the public chapter API to call `PublicGlossaryAnnotationsService.find_annotations()` so annotation logic is centralized.

### Acceptance criteria

1. WHEN the public chapter API loads a published chapter THEN it SHALL call `PublicGlossaryAnnotationsService.find_annotations()` or equivalent service method.
2. WHEN the service is called THEN it SHALL receive the novel/chapter context required for visibility and matching.
3. WHEN the service is called THEN it SHALL receive the text and/or reader blocks needed to compute offsets.
4. WHEN the service returns annotations THEN the API SHALL attach them to the response.
5. WHEN the service returns no annotations THEN the API SHALL attach an empty list.
6. WHEN the service raises an expected recoverable error THEN the API SHALL log a safe warning and return the chapter with empty annotations.
7. WHEN the chapter itself cannot be loaded THEN the annotation service SHALL NOT leak information about the chapter or glossary.

## Requirement 3: Public-safe annotation contract

### User story

As a frontend developer, I want each annotation to include enough safe information to render a reader highlight later.

### Acceptance criteria

1. WHEN an annotation is returned THEN it SHALL include a term identifier.
2. WHEN an annotation is returned THEN it SHALL include a display term or public label.
3. WHEN an annotation is returned THEN it SHALL include match text or enough offset information to identify the matched span.
4. WHEN an annotation is returned for text mode THEN it SHALL include valid start and end offsets relative to the returned text.
5. WHEN an annotation is returned for reader-block mode THEN it SHOULD include block index or block ID plus valid block-relative offsets.
6. WHEN a public definition is available and approved THEN the annotation MAY include the definition.
7. WHEN a source term is not safe for public display THEN it SHALL be omitted or replaced with a safe display value.
8. WHEN an annotation contains optional fields THEN those fields SHALL be JSON-compatible and public-safe.
9. WHEN annotations are serialized THEN they SHALL not include internal ORM objects or non-JSON values.

## Requirement 4: Glossary visibility filtering

### User story

As an operator, I want public annotations to expose only approved public glossary terms so draft or private glossary data cannot leak.

### Acceptance criteria

1. WHEN a glossary term is inactive THEN it SHALL NOT appear in public annotations.
2. WHEN a glossary term is unapproved or rejected THEN it SHALL NOT appear in public annotations.
3. WHEN a glossary term is private/internal-only THEN it SHALL NOT appear in public annotations.
4. WHEN a glossary term belongs to a different novel/context THEN it SHALL NOT appear in the chapter annotations.
5. WHEN a glossary alias is inactive or private THEN that alias SHALL NOT be exposed as a public match.
6. WHEN a glossary definition is private or admin-only THEN it SHALL NOT be exposed.
7. WHEN visibility metadata is ambiguous THEN the system SHALL prefer hiding the annotation.
8. WHEN the public chapter is unpublished THEN no glossary annotation data SHALL be exposed.
9. WHEN the public novel is unpublished THEN no glossary annotation data SHALL be exposed.

## Requirement 5: Text and reader block offset support

### User story

As a frontend developer, I want annotation offsets to correspond to the response format used by the reader.

### Acceptance criteria

1. WHEN the chapter response includes plain `text` THEN annotation offsets SHALL be relative to that returned text.
2. WHEN the chapter response includes `reader_blocks` THEN annotation offsets SHOULD be relative to the relevant block text.
3. WHEN block IDs are available THEN annotations SHOULD include block ID.
4. WHEN block IDs are not available THEN annotations SHOULD include block index.
5. WHEN both full text and reader blocks are returned THEN annotations SHALL use the project’s chosen canonical offset mode consistently.
6. WHEN offsets cannot be computed safely THEN the affected annotation SHALL be omitted.
7. WHEN offsets are returned THEN tests SHALL verify they point to the expected match text.
8. WHEN reader text is transformed before response THEN annotation matching SHALL use the transformed public text, not a mismatched internal representation.

## Requirement 6: Ordering and overlap behavior

### User story

As a frontend developer, I want annotations returned in deterministic order so rendering behavior is predictable.

### Acceptance criteria

1. WHEN annotations are returned THEN they SHALL be ordered deterministically.
2. WHEN annotations have block positions THEN they SHALL be ordered by block index and start offset.
3. WHEN annotations have text offsets THEN they SHALL be ordered by start offset.
4. WHEN multiple annotations start at the same offset THEN the longer match SHOULD appear first.
5. WHEN there are ties after offset and length THEN a stable term identifier or priority SHALL be used.
6. WHEN overlapping annotations are not supported THEN the service SHALL omit or resolve overlaps deterministically.
7. WHEN overlap handling is delegated to the service THEN the API SHALL not introduce inconsistent reordering.

## Requirement 7: Feature setting compatibility

### User story

As an operator, I want public annotation wiring to respect existing settings if annotation toggles already exist.

### Acceptance criteria

1. WHEN a global public glossary annotation setting exists and is disabled THEN the API SHALL return an empty annotations list.
2. WHEN a per-novel public glossary annotation setting exists and is disabled THEN the API SHALL return an empty annotations list for that novel.
3. WHEN settings do not exist yet THEN this spec SHALL not require creating them.
4. WHEN settings are added later THEN this API wiring SHALL be compatible with them.
5. WHEN annotations are disabled by settings THEN the API SHALL preserve the rest of the chapter response.
6. WHEN annotations are disabled by settings THEN the API SHOULD avoid unnecessary annotation lookup when practical.

## Requirement 8: Error isolation

### User story

As a reader, I want the chapter to load even if annotation lookup fails.

### Acceptance criteria

1. WHEN annotation lookup fails with a recoverable error THEN the public chapter API SHALL still return the chapter response.
2. WHEN annotation lookup fails THEN `glossary_annotations` SHALL be an empty list.
3. WHEN annotation lookup fails THEN the system SHALL log a safe warning.
4. WHEN annotation lookup returns malformed annotations THEN the API SHALL filter invalid annotations where practical.
5. WHEN all annotations are invalid THEN the API SHALL return an empty list.
6. WHEN annotation lookup failure occurs THEN public responses SHALL not expose stack traces or internal errors.
7. WHEN chapter loading fails independently THEN existing chapter error behavior SHALL remain unchanged.

## Requirement 9: Performance and limits

### User story

As an operator, I want annotation lookup to be bounded so public chapter loading remains fast.

### Acceptance criteria

1. WHEN annotation lookup runs THEN it SHALL use the existing efficient glossary matching service or indexed lookup where available.
2. WHEN annotation count exceeds configured maximum per chapter THEN the system SHALL truncate or limit returned annotations.
3. WHEN annotations are truncated THEN the API MAY omit truncation details from public response unless a public-safe field is defined.
4. WHEN annotation lookup exceeds configured timeout or fails due to performance guard THEN the API SHALL return an empty or partial safe annotation list according to implementation.
5. WHEN annotation lookup runs THEN it SHALL avoid N+1 queries for term definitions and aliases where practical.
6. WHEN no glossary terms are available for the novel THEN the service SHOULD return quickly with an empty list.
7. WHEN public chapter caching exists THEN annotation behavior SHALL be compatible with existing cache invalidation rules.

## Requirement 10: Security and privacy

### User story

As an operator, I want public annotation responses to avoid leaking private glossary, prompt, or moderation data.

### Acceptance criteria

1. WHEN annotations are returned THEN they SHALL NOT include private glossary notes.
2. WHEN annotations are returned THEN they SHALL NOT include admin-only moderation metadata.
3. WHEN annotations are returned THEN they SHALL NOT include inactive aliases.
4. WHEN annotations are returned THEN they SHALL NOT include rejected or draft glossary terms.
5. WHEN annotations are returned THEN they SHALL NOT include raw prompt instructions.
6. WHEN annotations are returned THEN they SHALL NOT include raw model diagnostics.
7. WHEN annotations are returned THEN they SHALL NOT include provider errors, tokens, or secrets.
8. WHEN annotation errors are logged THEN logs SHALL not include secrets or full private glossary data.
9. WHEN public users access a chapter THEN they SHALL only see annotations for content they are already allowed to read.

## Requirement 11: API compatibility

### User story

As a maintainer, I want this field to be additive so existing public reader clients do not break.

### Acceptance criteria

1. WHEN the new field is added THEN existing response fields SHALL not be removed.
2. WHEN the new field is added THEN existing response field names SHALL not change.
3. WHEN annotations are unavailable THEN the field SHALL default to an empty list.
4. WHEN clients do not use annotations THEN reader rendering SHALL continue as before.
5. WHEN tests validate the public chapter response schema THEN they SHALL be updated for the additive field.
6. WHEN serialized responses are compared in snapshots THEN snapshots SHALL be updated only for the new field.

## Requirement 12: Test coverage

### User story

As a maintainer, I want tests for public annotation wiring so annotation exposure is safe and stable.

### Acceptance criteria

1. WHEN tests run THEN they SHALL verify public chapter responses include `glossary_annotations`.
2. WHEN tests run THEN they SHALL verify the annotation service is called for published chapters.
3. WHEN tests run THEN they SHALL verify empty annotations return an empty list.
4. WHEN tests run THEN they SHALL verify approved active terms are returned.
5. WHEN tests run THEN they SHALL verify inactive terms are hidden.
6. WHEN tests run THEN they SHALL verify unapproved/rejected terms are hidden.
7. WHEN tests run THEN they SHALL verify private/internal terms are hidden.
8. WHEN tests run THEN they SHALL verify unpublished chapters do not expose annotations.
9. WHEN tests run THEN they SHALL verify unpublished novels do not expose annotations.
10. WHEN tests run THEN they SHALL verify offsets match returned text or reader blocks.
11. WHEN tests run THEN they SHALL verify deterministic ordering.
12. WHEN tests run THEN they SHALL verify service failure does not fail chapter response.
13. WHEN tests run THEN they SHALL verify response compatibility with old no-annotation cases.
14. WHEN settings already exist THEN tests SHALL verify disabled settings return an empty annotation list.

## Requirement 13: Completion verification

### User story

As a maintainer, I want a clear completion check so this feature wiring is not considered done until the public API returns safe annotations.

### Acceptance criteria

1. WHEN a published chapter contains approved glossary terms THEN the public chapter API SHALL return annotation records.
2. WHEN a published chapter has no matching glossary terms THEN the public chapter API SHALL return `glossary_annotations: []`.
3. WHEN an unapproved or private term matches chapter text THEN it SHALL not appear in public annotations.
4. WHEN annotation lookup fails in a controlled test THEN the chapter response SHALL still succeed with empty annotations.
5. WHEN frontend rendering has not been implemented yet THEN the public reader SHALL still work unchanged.
6. WHEN API response is inspected THEN `glossary_annotations` SHALL be present and JSON-compatible.
