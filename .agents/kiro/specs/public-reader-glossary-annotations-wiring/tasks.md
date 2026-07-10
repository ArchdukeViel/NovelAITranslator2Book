# tasks.md

# Tasks: Public Reader Glossary Annotations Wiring

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect public chapter API endpoint and response model.
  * [ ] 0.2 Inspect public novel/chapter publication checks.
  * [ ] 0.3 Inspect public reader rendering data: `text`, `reader_blocks`, or both.
  * [ ] 0.4 Inspect `PublicGlossaryAnnotationsService.find_annotations()` signature.
  * [ ] 0.5 Inspect glossary term model fields for status, approval, active state, aliases, definitions, and visibility.
  * [ ] 0.6 Inspect existing feature setting pattern for global/per-novel annotation toggles, if any.
  * [ ] 0.7 Inspect public chapter caching behavior, if any.
  * [ ] 0.8 Inspect existing backend tests for public reader and glossary services.
  * [ ] 0.9 Identify whether response schemas are generated, snapshotted, or manually typed.

* [ ] 1. Define public annotation response contract

  * [ ] 1.1 Define `glossary_annotations` top-level response field. (REQ-1)
  * [ ] 1.2 Define public annotation object schema. (REQ-3)
  * [ ] 1.3 Include `term_id`. (REQ-3)
  * [ ] 1.4 Include public display term. (REQ-3)
  * [ ] 1.5 Include public definition only when safe and approved. (REQ-3, REQ-4)
  * [ ] 1.6 Include match text or safe match context. (REQ-3)
  * [ ] 1.7 Include text offsets for text mode. (REQ-5)
  * [ ] 1.8 Include block index or block ID for reader-block mode. (REQ-5)
  * [ ] 1.9 Define optional fields such as match type, confidence, and annotation ID. (REQ-3)
  * [ ] 1.10 Document fields that must never be exposed publicly. (REQ-10)

* [ ] 2. Update public chapter response model

  * [ ] 2.1 Add `glossary_annotations` to response schema/model. (REQ-1, REQ-11)
  * [ ] 2.2 Default `glossary_annotations` to an empty list. (REQ-1, REQ-11)
  * [ ] 2.3 Ensure old activities/chapters without annotations serialize correctly. (REQ-11)
  * [ ] 2.4 Ensure OpenAPI/generated schema includes the field if applicable. (REQ-1)
  * [ ] 2.5 Update response snapshots only for additive field changes. (REQ-11, REQ-12)

* [ ] 3. Verify service output safety

  * [ ] 3.1 Confirm `PublicGlossaryAnnotationsService.find_annotations()` filters unpublished/unavailable novel context. (REQ-4)
  * [ ] 3.2 Confirm service filters inactive terms. (REQ-4)
  * [ ] 3.3 Confirm service filters unapproved/rejected terms. (REQ-4)
  * [ ] 3.4 Confirm service filters private/internal terms. (REQ-4)
  * [ ] 3.5 Confirm service filters inactive/private aliases. (REQ-4)
  * [ ] 3.6 Confirm service omits private/admin-only definitions. (REQ-4, REQ-10)
  * [ ] 3.7 Add API-level safety filter if service does not guarantee all visibility rules. (REQ-4, REQ-10)
  * [ ] 3.8 Add tests for each visibility rule. (REQ-4, REQ-12)

* [ ] 4. Wire annotation service into public chapter endpoint

  * [ ] 4.1 Locate the final point where public chapter text/reader blocks are loaded. (REQ-2)
  * [ ] 4.2 Call `PublicGlossaryAnnotationsService.find_annotations()` after publication checks pass. (REQ-2)
  * [ ] 4.3 Pass novel ID and chapter ID. (REQ-2)
  * [ ] 4.4 Pass public text and/or reader blocks. (REQ-2, REQ-5)
  * [ ] 4.5 Pass language pair or translation context if required by service. (REQ-2)
  * [ ] 4.6 Attach returned annotations to response. (REQ-1, REQ-2)
  * [ ] 4.7 Return empty list when service returns no matches. (REQ-1, REQ-2)
  * [ ] 4.8 Ensure annotation service is not called for unpublished/unavailable chapters. (REQ-2, REQ-4)
  * [ ] 4.9 Add tests verifying service invocation and non-invocation paths. (REQ-2, REQ-12)

* [ ] 5. Support text offset mode

  * [ ] 5.1 Determine canonical text string returned by public chapter API. (REQ-5)
  * [ ] 5.2 Ensure annotation offsets are computed against that returned text. (REQ-5)
  * [ ] 5.3 Validate `start_offset` and `end_offset` bounds before returning annotations. (REQ-5)
  * [ ] 5.4 Filter annotations with invalid offsets. (REQ-5, REQ-8)
  * [ ] 5.5 Add tests verifying offsets map to expected `match_text`. (REQ-5, REQ-12)
  * [ ] 5.6 Add tests for transformed text if public response differs from stored text. (REQ-5, REQ-12)

* [ ] 6. Support reader block offset mode

  * [ ] 6.1 Determine reader block text field and stable block identifier, if available. (REQ-5)
  * [ ] 6.2 Ensure annotations include block ID when available. (REQ-5)
  * [ ] 6.3 Ensure annotations include block index when block ID is unavailable. (REQ-5)
  * [ ] 6.4 Ensure offsets are relative to block text. (REQ-5)
  * [ ] 6.5 Validate block index/ID and offset bounds. (REQ-5)
  * [ ] 6.6 Filter annotations with invalid block references. (REQ-5, REQ-8)
  * [ ] 6.7 Add tests for block-relative annotations. (REQ-5, REQ-12)

* [ ] 7. Add deterministic ordering and overlap handling

  * [ ] 7.1 Confirm whether service already resolves overlaps. (REQ-6)
  * [ ] 7.2 If needed, sort annotations by block index and start offset. (REQ-6)
  * [ ] 7.3 If needed, sort same-start annotations by longer match first. (REQ-6)
  * [ ] 7.4 Add stable tie-breaker using term priority or term ID. (REQ-6)
  * [ ] 7.5 Avoid introducing inconsistent overlap behavior in API layer. (REQ-6)
  * [ ] 7.6 Add tests for deterministic ordering. (REQ-6, REQ-12)
  * [ ] 7.7 Add tests for overlap behavior if service supports or resolves overlaps. (REQ-6, REQ-12)

* [ ] 8. Respect existing annotation settings if present

  * [ ] 8.1 Check for existing global public annotation setting. (REQ-7)
  * [ ] 8.2 Check for existing per-novel annotation setting. (REQ-7)
  * [ ] 8.3 If global setting exists and is disabled, return empty annotations. (REQ-7)
  * [ ] 8.4 If per-novel setting exists and is disabled, return empty annotations for that novel. (REQ-7)
  * [ ] 8.5 Avoid service lookup when annotations are disabled by settings where practical. (REQ-7)
  * [ ] 8.6 Do not create new settings in this spec if they do not exist. (REQ-7)
  * [ ] 8.7 Add tests for existing settings behavior if settings exist. (REQ-7, REQ-12)

* [ ] 9. Add error isolation

  * [ ] 9.1 Wrap annotation lookup in safe error handling. (REQ-8)
  * [ ] 9.2 On recoverable service failure, return `glossary_annotations: []`. (REQ-8)
  * [ ] 9.3 Log safe warning with novel/chapter context. (REQ-8, REQ-10)
  * [ ] 9.4 Filter malformed annotation records where practical. (REQ-8)
  * [ ] 9.5 Ensure public response does not expose stack traces or internal errors. (REQ-8, REQ-10)
  * [ ] 9.6 Preserve existing chapter loading errors for actual chapter failures. (REQ-8)
  * [ ] 9.7 Add tests for service exception and malformed annotation output. (REQ-8, REQ-12)

* [ ] 10. Add performance limits

  * [ ] 10.1 Add or reuse max annotations per chapter setting. (REQ-9)
  * [ ] 10.2 Add annotation lookup timeout if service infrastructure supports it. (REQ-9)
  * [ ] 10.3 Ensure service avoids N+1 term/alias/definition queries where practical. (REQ-9)
  * [ ] 10.4 Limit returned annotations to configured maximum. (REQ-9)
  * [ ] 10.5 Ensure no-glossary chapters return quickly. (REQ-9)
  * [ ] 10.6 Verify cache compatibility if public chapter caching exists. (REQ-9)
  * [ ] 10.7 Add tests for annotation limit and no-glossary path. (REQ-9, REQ-12)

* [ ] 11. Add security and redaction checks

  * [ ] 11.1 Ensure annotations do not include private glossary notes. (REQ-10)
  * [ ] 11.2 Ensure annotations do not include moderation metadata. (REQ-10)
  * [ ] 11.3 Ensure annotations do not include raw prompt instructions. (REQ-10)
  * [ ] 11.4 Ensure annotations do not include raw model diagnostics. (REQ-10)
  * [ ] 11.5 Ensure annotations do not include provider errors, tokens, or secrets. (REQ-10)
  * [ ] 11.6 Ensure logs do not include private glossary data or secrets. (REQ-10)
  * [ ] 11.7 Ensure public users only receive annotations for chapters they can read. (REQ-10)
  * [ ] 11.8 Add security-focused tests for hidden/private fields. (REQ-10, REQ-12)

* [ ] 12. Update public reader API tests

  * [ ] 12.1 Test response includes `glossary_annotations`. (REQ-1, REQ-12)
  * [ ] 12.2 Test no annotations returns empty list. (REQ-1, REQ-12)
  * [ ] 12.3 Test service is called for published chapter. (REQ-2, REQ-12)
  * [ ] 12.4 Test service is not called for unpublished chapter. (REQ-2, REQ-4, REQ-12)
  * [ ] 12.5 Test approved active term appears. (REQ-4, REQ-12)
  * [ ] 12.6 Test inactive term hidden. (REQ-4, REQ-12)
  * [ ] 12.7 Test unapproved/rejected term hidden. (REQ-4, REQ-12)
  * [ ] 12.8 Test private/internal term hidden. (REQ-4, REQ-12)
  * [ ] 12.9 Test private alias hidden. (REQ-4, REQ-12)
  * [ ] 12.10 Test text offsets. (REQ-5, REQ-12)
  * [ ] 12.11 Test reader block offsets if reader blocks exist. (REQ-5, REQ-12)
  * [ ] 12.12 Test deterministic ordering. (REQ-6, REQ-12)
  * [ ] 12.13 Test service failure returns empty annotations and chapter still loads. (REQ-8, REQ-12)
  * [ ] 12.14 Test annotation limits. (REQ-9, REQ-12)
  * [ ] 12.15 Test additive response compatibility. (REQ-11, REQ-12)

* [ ] 13. Documentation

  * [ ] 13.1 Document public chapter `glossary_annotations` field. (REQ-1)
  * [ ] 13.2 Document annotation object fields. (REQ-3)
  * [ ] 13.3 Document offset mode for text and/or reader blocks. (REQ-5)
  * [ ] 13.4 Document visibility rules. (REQ-4, REQ-10)
  * [ ] 13.5 Document failure behavior: annotation lookup failure returns empty list. (REQ-8)
  * [ ] 13.6 Document that frontend rendering is handled by a separate spec. (REQ-13)
  * [ ] 13.7 Document settings compatibility if existing settings are respected. (REQ-7)

* [ ] 14. Completion verification

  * [ ] 14.1 Create or use a published novel/chapter with approved glossary terms. (REQ-13)
  * [ ] 14.2 Call public chapter API and verify `glossary_annotations` contains records. (REQ-13)
  * [ ] 14.3 Call public chapter API for a chapter with no matches and verify empty list. (REQ-13)
  * [ ] 14.4 Add unapproved/private matching term and verify it is hidden. (REQ-4, REQ-13)
  * [ ] 14.5 Simulate annotation service failure and verify chapter still loads. (REQ-8, REQ-13)
  * [ ] 14.6 Verify existing reader frontend still renders without annotation UI changes. (REQ-11, REQ-13)
  * [ ] 14.7 Verify response is JSON-compatible and schema-valid. (REQ-1, REQ-13)
  * [ ] 14.8 Mark `public-reader-glossary-annotations-wiring` complete only after public chapter API returns safe annotations.
