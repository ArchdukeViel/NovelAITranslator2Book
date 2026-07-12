# tasks.md

# Tasks: Frontend Glossary Annotation Rendering

## Task List

* [x] 0. Preflight review

  * [x] 0.1 Inspect public reader page/component structure.
  * [x] 0.2 Inspect chapter API client and response types.
  * [x] 0.3 Inspect whether reader uses `text`, `reader_blocks`, or both.
  * [x] 0.4 Inspect existing reader block rendering components.
  * [x] 0.5 Inspect reader settings/preference patterns.
  * [x] 0.6 Inspect tooltip/popover component library or existing UI primitives.
  * [x] 0.7 Inspect existing reader theme/design tokens.
  * [x] 0.8 Inspect frontend test setup for reader components.
  * [x] 0.9 Inspect accessibility conventions for interactive inline elements.

* [x] 1. Define frontend annotation types

  * [x] 1.1 Add `GlossaryAnnotation` type/interface. (REQ-1)
  * [x] 1.2 Include `term_id`. (REQ-1)
  * [x] 1.3 Include `display_term`. (REQ-5)
  * [x] 1.4 Include optional `definition`. (REQ-5)
  * [x] 1.5 Include optional `source_term`. (REQ-5)
  * [x] 1.6 Include `start_offset` and `end_offset`. (REQ-2, REQ-3)
  * [x] 1.7 Include optional `block_id` and `block_index`. (REQ-3)
  * [x] 1.8 Include optional `match_text` and `match_type`. (REQ-2)
  * [x] 1.9 Update chapter response type to include optional `glossary_annotations`. (REQ-1)

* [x] 2. Add annotation validation helper

  * [x] 2.1 Validate annotation object shape. (REQ-1, REQ-11)
  * [x] 2.2 Validate text offsets against text length. (REQ-2)
  * [x] 2.3 Validate block offsets against block text length. (REQ-3)
  * [x] 2.4 Validate block ID/index references. (REQ-3)
  * [x] 2.5 Optionally validate `match_text` against rendered span. (REQ-2)
  * [x] 2.6 Skip invalid annotations. (REQ-11)
  * [x] 2.7 Add tests for valid, missing fields, invalid offsets, invalid block reference, and mismatch cases. (REQ-2, REQ-3, REQ-11, REQ-12)

* [x] 3. Add annotation sorting and overlap helper

  * [x] 3.1 Sort annotations by start offset. (REQ-4)
  * [x] 3.2 Prefer longer match for same start offset. (REQ-4)
  * [x] 3.3 Add stable tie-breaker by term ID or original index. (REQ-4)
  * [x] 3.4 Deduplicate identical spans where practical. (REQ-4)
  * [x] 3.5 Skip overlapping annotations after first accepted match. (REQ-4)
  * [x] 3.6 Add tests for ordering, same-start matches, duplicates, overlaps, and deterministic output. (REQ-4, REQ-12)

* [x] 4. Add text segmentation helper

  * [x] 4.1 Create helper that converts text plus annotations into render segments. (REQ-2)
  * [x] 4.2 Include plain text segments. (REQ-2)
  * [x] 4.3 Include annotation segments. (REQ-2)
  * [x] 4.4 Preserve all original text. (REQ-2)
  * [x] 4.5 Handle annotations at beginning of text. (REQ-2)
  * [x] 4.6 Handle annotations at end of text. (REQ-2)
  * [x] 4.7 Return plain segment when no valid annotations exist. (REQ-1, REQ-2)
  * [x] 4.8 Add tests for basic split, edge positions, no annotations, invalid annotations, and full text preservation. (REQ-2, REQ-12)

* [x] 5. Add `AnnotatedText` component

  * [x] 5.1 Create component accepting text and annotations. (REQ-2)
  * [x] 5.2 Render plain segments as normal escaped text. (REQ-2, REQ-8)
  * [x] 5.3 Render annotation segments with highlight component. (REQ-2)
  * [x] 5.4 Support disabled annotations prop. (REQ-6)
  * [x] 5.5 Handle malformed annotation input gracefully. (REQ-11)
  * [x] 5.6 Memoize segment calculation where practical. (REQ-10)
  * [x] 5.7 Add component tests for normal text, highlighted text, disabled state, and malformed annotations. (REQ-2, REQ-6, REQ-11, REQ-12)

* [x] 6. Add `GlossaryAnnotationHighlight` component

  * [x] 6.1 Render highlighted term text. (REQ-2, REQ-5)
  * [x] 6.2 Attach annotation metadata for tooltip/popover. (REQ-5)
  * [x] 6.3 Add focusable behavior when interactive. (REQ-7)
  * [x] 6.4 Add hover/focus/tap handlers according to UI pattern. (REQ-5, REQ-7)
  * [x] 6.5 Add visible focus state. (REQ-7)
  * [x] 6.6 Use theme/design tokens for styling. (REQ-9)
  * [x] 6.7 Add tests for rendering, interaction, focusability, and theme class/token usage where practical. (REQ-5, REQ-7, REQ-9, REQ-12)

* [x] 7. Add tooltip/popover component

  * [x] 7.1 Reuse existing tooltip/popover primitive if available. (REQ-5)
  * [x] 7.2 Show display term. (REQ-5)
  * [x] 7.3 Show definition when available. (REQ-5)
  * [x] 7.4 Show source term only if provided and safe. (REQ-5)
  * [x] 7.5 Add fallback for missing definition. (REQ-5)
  * [x] 7.6 Add Escape close behavior where supported. (REQ-7)
  * [x] 7.7 Add accessible label/description. (REQ-7)
  * [x] 7.8 Add tests for content, missing definition, hover/focus/click behavior, Escape close, and accessibility attributes. (REQ-5, REQ-7, REQ-12)

* [x] 8. Wire text-mode reader rendering

  * [x] 8.1 Locate plain text reader rendering path. (REQ-2)
  * [x] 8.2 Pass `glossary_annotations` to `AnnotatedText`. (REQ-2)
  * [x] 8.3 Filter annotations without block references for text mode. (REQ-2)
  * [x] 8.4 Preserve existing reader layout and typography. (REQ-9)
  * [x] 8.5 Confirm chapters without annotations render unchanged. (REQ-1)
  * [x] 8.6 Add integration tests for plain text reader with and without annotations. (REQ-1, REQ-2, REQ-12)

* [x] 9. Wire reader-block rendering

  * [x] 9.1 Locate reader block component. (REQ-3)
  * [x] 9.2 Group annotations by `block_id`. (REQ-3, REQ-10)
  * [x] 9.3 Fall back to grouping by `block_index`. (REQ-3)
  * [x] 9.4 Pass block-specific annotations to `AnnotatedText`. (REQ-3)
  * [x] 9.5 Preserve existing block rendering behavior. (REQ-3, REQ-9)
  * [x] 9.6 Skip unsupported non-text blocks. (REQ-3)
  * [x] 9.7 Add integration tests for block annotations, invalid block references, and unsupported block types. (REQ-3, REQ-12)

* [x] 10. Add reader preference toggle

  * [x] 10.1 Add `showGlossaryAnnotations` preference key. (REQ-6)
  * [x] 10.2 Default preference to enabled. (REQ-6)
  * [x] 10.3 Persist preference in existing reader preference store or localStorage. (REQ-6)
  * [x] 10.4 Add toggle to reader settings UI. (REQ-6)
  * [x] 10.5 Apply preference to text mode and block mode. (REQ-6)
  * [x] 10.6 Disable tooltips/popovers when annotations are disabled. (REQ-6)
  * [x] 10.7 Handle preference storage failure gracefully. (REQ-6)
  * [x] 10.8 Add tests for default enabled, toggle off, toggle on, persistence, and storage failure. (REQ-6, REQ-12)

* [x] 11. Add styling and theme support

  * [x] 11.1 Add default highlight style using design tokens. (REQ-9)
  * [x] 11.2 Add hover style. (REQ-9)
  * [x] 11.3 Add focus style. (REQ-7, REQ-9)
  * [x] 11.4 Add active/open style. (REQ-9)
  * [x] 11.5 Verify light theme readability. (REQ-9)
  * [x] 11.6 Verify dark theme readability. (REQ-9)
  * [x] 11.7 Verify mobile layout does not overflow. (REQ-9)
  * [x] 11.8 Add visual/unit tests where project conventions support them. (REQ-9, REQ-12)

* [x] 12. Add security hardening

  * [x] 12.1 Ensure annotation fields are rendered as text, not raw HTML. (REQ-8)
  * [x] 12.2 Avoid `dangerouslySetInnerHTML` for annotation rendering. (REQ-8)
  * [x] 12.3 Escape/sanitize definition content. (REQ-8)
  * [x] 12.4 Ensure script tags in annotation data do not execute. (REQ-8)
  * [x] 12.5 Ensure event-handler strings in annotation data do not execute. (REQ-8)
  * [x] 12.6 Avoid rendering annotation URLs as links unless separately sanitized. (REQ-8)
  * [x] 12.7 Add tests with malicious display term, definition, source term, and match text. (REQ-8, REQ-12)

* [x] 13. Add accessibility pass

  * [x] 13.1 Ensure highlights are keyboard focusable. (REQ-7)
  * [x] 13.2 Ensure tooltip/popover is associated with highlight. (REQ-7)
  * [x] 13.3 Ensure focus indicator is visible. (REQ-7)
  * [x] 13.4 Ensure Escape closes tooltip/popover where supported. (REQ-7)
  * [x] 13.5 Ensure tab order follows reading order. (REQ-7)
  * [x] 13.6 Ensure screen reader text includes term and definition where practical. (REQ-7)
  * [x] 13.7 Add accessibility tests where tooling supports them. (REQ-7, REQ-12)

* [x] 14. Add performance safeguards

  * [x] 14.1 Group annotations by block before rendering. (REQ-10)
  * [x] 14.2 Avoid repeated sorting for unchanged inputs where practical. (REQ-10)
  * [x] 14.3 Memoize processed segments. (REQ-10)
  * [x] 14.4 Skip segmentation when annotations disabled. (REQ-10)
  * [x] 14.5 Avoid creating excessive tooltip instances if shared tooltip system exists. (REQ-10)
  * [x] 14.6 Add stress test or unit test with many annotations where practical. (REQ-10, REQ-12)

* [x] 15. Add error boundary or safe fallback

  * [x] 15.1 Wrap annotation processing in safe fallback helper. (REQ-11)
  * [x] 15.2 On processing failure, render unannotated text. (REQ-11)
  * [x] 15.3 On tooltip failure, keep highlight or text visible. (REQ-11)
  * [x] 15.4 Avoid showing raw technical errors to readers. (REQ-11)
  * [x] 15.5 Add tests for processing exception and tooltip exception if practical. (REQ-11, REQ-12)

* [x] 16. Frontend test coverage pass

  * [x] 16.1 Test chapter without `glossary_annotations`. (REQ-1, REQ-12)
  * [x] 16.2 Test empty `glossary_annotations`. (REQ-1, REQ-12)
  * [x] 16.3 Test text-mode highlight rendering. (REQ-2, REQ-12)
  * [x] 16.4 Test reader-block highlight rendering by block ID. (REQ-3, REQ-12)
  * [x] 16.5 Test reader-block highlight rendering by block index. (REQ-3, REQ-12)
  * [x] 16.6 Test tooltip content. (REQ-5, REQ-12)
  * [x] 16.7 Test missing definition fallback. (REQ-5, REQ-12)
  * [x] 16.8 Test preference disabled state. (REQ-6, REQ-12)
  * [x] 16.9 Test invalid offset skipping. (REQ-2, REQ-11, REQ-12)
  * [x] 16.10 Test overlap handling. (REQ-4, REQ-12)
  * [x] 16.11 Test duplicate handling where implemented. (REQ-4, REQ-12)
  * [x] 16.12 Test malicious HTML/script escaping. (REQ-8, REQ-12)
  * [x] 16.13 Test keyboard focus behavior. (REQ-7, REQ-12)
  * [x] 16.14 Test malformed annotation resilience. (REQ-11, REQ-12)

* [x] 17. Documentation

  * [x] 17.1 Document frontend annotation rendering contract. (REQ-1)
  * [x] 17.2 Document text offset behavior. (REQ-2)
  * [x] 17.3 Document block offset behavior. (REQ-3)
  * [x] 17.4 Document overlap handling policy. (REQ-4)
  * [x] 17.5 Document reader preference key. (REQ-6)
  * [x] 17.6 Document accessibility behavior. (REQ-7)
  * [x] 17.7 Document HTML safety rules. (REQ-8)
  * [x] 17.8 Document troubleshooting for invalid annotation offsets. (REQ-11)

* [x] 18. Completion verification

  * [x] 18.1 Load a public chapter with no annotations and verify rendering is unchanged. (REQ-1, REQ-13)
  * [x] 18.2 Load a public chapter with text-mode annotations and verify highlights appear. (REQ-2, REQ-13)
  * [x] 18.3 Load a public chapter with block annotations and verify highlights appear in correct blocks. (REQ-3, REQ-13)
  * [x] 18.4 Open a highlighted term and verify display term/definition appears. (REQ-5, REQ-13)
  * [x] 18.5 Disable glossary highlights and verify highlights disappear. (REQ-6, REQ-13)
  * [x] 18.6 Use keyboard navigation and verify highlights are reachable. (REQ-7, REQ-13)
  * [x] 18.7 Test malicious annotation fixture and verify no HTML/script executes. (REQ-8, REQ-13)
  * [x] 18.8 Test malformed annotations and verify chapter remains readable. (REQ-11, REQ-13)
  * [x] 18.9 Mark `frontend-glossary-annotation-rendering` complete only after highlights, tooltips, preference toggle, and safety tests pass.
