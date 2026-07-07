# Tasks: Public Reader Glossary Annotations

## Task List

- [ ] 1. Preflight Reader and Glossary Review
  - [ ] 1.1 Inspect public reader chapter API response shape.
  - [ ] 1.2 Inspect public reader frontend rendering of `text` and `reader_blocks`.
  - [ ] 1.3 Inspect glossary DB models for status, approval, aliases, definitions, and visibility-related fields.
  - [ ] 1.4 Inspect existing public novel/chapter publication checks.
  - [ ] 1.5 Inspect existing settings pattern for feature flags.
  - [ ] 1.6 Inspect frontend local preference/toggle patterns.
  - [ ] 1.7 Inspect existing public reader backend and frontend tests.

- [ ] 2. Define Public Annotation Contract
  - [ ] 2.1 Define `glossary_annotations` response field. (REQ-2.1)
  - [ ] 2.2 Include `term_id`. (REQ-2.2)
  - [ ] 2.3 Include safe `source_term` when allowed. (REQ-2.3)
  - [ ] 2.4 Include `display_term` or `translation`. (REQ-2.4)
  - [ ] 2.5 Include optional `reading`, `term_type`, `short_definition`, and public-safe `aliases`. (REQ-2.5)
  - [ ] 2.6 Include matched surface forms. (REQ-2.6)
  - [ ] 2.7 Include block offsets when block-level matching is used.
  - [ ] 2.8 Bound payload size. (REQ-2.7)

- [ ] 3. Add Public Glossary Visibility Policy
  - [ ] 3.1 Add helper to select public-safe glossary terms. (REQ-1)
  - [ ] 3.2 Include approved entries only. (REQ-1.1)
  - [ ] 3.3 Exclude candidate, pending, rejected, internal, and admin-only entries. (REQ-1.2)
  - [ ] 3.4 Use `public_visible` or equivalent field if available. (REQ-1.3)
  - [ ] 3.5 If no visibility field exists, default to conservative exposure. (REQ-1.4)
  - [ ] 3.6 Ensure diagnostics and workflow metadata are never exposed. (REQ-1.5, REQ-6)

- [ ] 4. Add Feature Configuration
  - [ ] 4.1 Add global setting to enable/disable public glossary annotations. (REQ-5.4)
  - [ ] 4.2 Add max public glossary terms setting. (REQ-7.1)
  - [ ] 4.3 Add max matches per term setting. (REQ-7.1)
  - [ ] 4.4 Add max total matches setting. (REQ-7.1)
  - [ ] 4.5 Add per-novel metadata override if consistent with reader settings. (REQ-5.5)

- [ ] 5. Implement Annotation Matching Service
  - [ ] 5.1 Add `PublicGlossaryAnnotationService` or equivalent.
  - [ ] 5.2 Match translated chapter text, not raw source text. (REQ-3.1)
  - [ ] 5.3 Match approved English translations/display terms. (REQ-3.2)
  - [ ] 5.4 Match public-safe aliases. (REQ-3.3)
  - [ ] 5.5 Use case-insensitive Latin-script matching. (REQ-3.5)
  - [ ] 5.6 Use word-boundary-aware matching to avoid substring false positives. (REQ-3.4)
  - [ ] 5.7 Preserve translated text unchanged. (REQ-3.6)
  - [ ] 5.8 Support `reader_blocks` block-level matching. (REQ-3.7)
  - [ ] 5.9 Sort longer terms first and resolve overlaps deterministically. (REQ-4.4)
  - [ ] 5.10 Enforce max term and match limits. (REQ-7.1)

- [ ] 6. Integrate Backend Public Chapter Response
  - [ ] 6.1 In public `get_chapter`, build annotations after translated text/reader blocks are available. (REQ-2)
  - [ ] 6.2 Return `glossary_annotations` when enabled. (REQ-2.1)
  - [ ] 6.3 Return `glossary_annotations: []` when disabled or no public terms match. (REQ-5.7)
  - [ ] 6.4 Return empty annotations for chapter shell/unavailable responses. (REQ-8.3)
  - [ ] 6.5 Keep response changes additive. (REQ-8.1)
  - [ ] 6.6 Ensure publication checks are unchanged and enforced. (REQ-6.7)

- [ ] 7. Add Optional Annotation Cache
  - [ ] 7.1 Decide whether initial implementation needs cache or bounded matching is enough. (REQ-7.6)
  - [ ] 7.2 If caching, key by novel ID, chapter ID, active version ID, and glossary revision. (REQ-7.3)
  - [ ] 7.3 Vary/invalidate cache when active translation version changes. (REQ-7.4)
  - [ ] 7.4 Vary/invalidate cache when public glossary revision changes. (REQ-7.5)

- [ ] 8. Implement Frontend Annotation Rendering
  - [ ] 8.1 Render annotations from block-level matches. (REQ-4.3)
  - [ ] 8.2 Wrap matched text without changing original text content. (REQ-4.3, REQ-8.5)
  - [ ] 8.3 Avoid nested/overlapping highlights. (REQ-4.4)
  - [ ] 8.4 Add hover/focus/tap tooltip or popover. (REQ-4.2)
  - [ ] 8.5 Ensure keyboard accessibility. (REQ-4.6)
  - [ ] 8.6 Ensure mobile layout works. (REQ-4.5)
  - [ ] 8.7 Ensure reader remains usable when annotations are unavailable. (REQ-4.7)

- [ ] 9. Add Reader Toggle
  - [ ] 9.1 Add show/hide glossary annotations control. (REQ-5.1)
  - [ ] 9.2 Set default from deployment/frontend setting. (REQ-5.2)
  - [ ] 9.3 Persist preference locally if existing patterns support it. (REQ-5.3)
  - [ ] 9.4 Render plain text when annotations are disabled. (REQ-5.1)

- [ ] 10. Security and Privacy Review
  - [ ] 10.1 Confirm status history is not exposed. (REQ-6.1)
  - [ ] 10.2 Confirm reviewer notes are not exposed. (REQ-6.2)
  - [ ] 10.3 Confirm prompt/glossary diagnostics are not exposed. (REQ-6.3)
  - [ ] 10.4 Confirm editor QA diagnostics are not exposed. (REQ-6.4)
  - [ ] 10.5 Confirm confidence/internal scores are not exposed unless explicitly public-safe. (REQ-6.5)
  - [ ] 10.6 Confirm unpublished novels/chapters cannot be accessed via annotations. (REQ-6.6)

- [ ] 11. Add Backend Tests
  - [ ] 11.1 Test approved public glossary terms are exposed. (REQ-9.1)
  - [ ] 11.2 Test pending/rejected/internal terms are not exposed. (REQ-9.2)
  - [ ] 11.3 Test matching finds approved translation in chapter text. (REQ-9.3)
  - [ ] 11.4 Test matching avoids substring false positives. (REQ-9.4)
  - [ ] 11.5 Test overlapping matches resolve deterministically.
  - [ ] 11.6 Test public chapter response includes annotations when enabled. (REQ-9.5)
  - [ ] 11.7 Test public chapter response returns empty/omits annotations when disabled. (REQ-9.6)
  - [ ] 11.8 Test public response does not expose admin diagnostics. (REQ-9.7)
  - [ ] 11.9 Test chapter shell response returns empty annotations.

- [ ] 12. Add Frontend Tests
  - [ ] 12.1 Test annotation rendering preserves text and paragraph structure. (REQ-9.8)
  - [ ] 12.2 Test tooltip/popover displays public-safe details.
  - [ ] 12.3 Test toggle hides annotations.
  - [ ] 12.4 Test keyboard focus opens/closes annotation UI. (REQ-9.9)
  - [ ] 12.5 Test mobile viewport does not overlap or clip annotation UI. (REQ-9.9)

- [ ] 13. Backward Compatibility Checks
  - [ ] 13.1 Confirm clients ignoring `glossary_annotations` render as before. (REQ-8.2)
  - [ ] 13.2 Confirm public reader availability behavior remains intact. (REQ-8.3)
  - [ ] 13.3 Confirm glossary admin/editor features remain unchanged. (REQ-8.4)
  - [ ] 13.4 Confirm translated text storage is not modified. (REQ-8.5)

- [ ] 14. Run Verification
  - [ ] 14.1 Run focused backend annotation tests.
  - [ ] 14.2 Run existing public reader backend tests.
  - [ ] 14.3 Run focused frontend annotation tests.
  - [ ] 14.4 Run existing public reader frontend tests.
  - [ ] 14.5 Run `ruff check` on changed backend files and tests.
  - [ ] 14.6 Run frontend lint/type/test commands if UI changed.
  - [ ] 14.7 Fix test, lint, and type failures caused by this work.

- [ ] 15. Final Acceptance Review
  - [ ] 15.1 Verify public chapter response includes annotations when enabled.
  - [ ] 15.2 Verify only approved public-safe glossary entries are exposed.
  - [ ] 15.3 Verify matching finds translated terms and avoids obvious false positives.
  - [ ] 15.4 Verify reader rendering preserves original text and paragraph structure.
  - [ ] 15.5 Verify reader has show/hide annotation control.
  - [ ] 15.6 Verify public APIs do not expose admin diagnostics or unpublished glossary data.
  - [ ] 15.7 Verify feature is bounded for response size and matching cost.
  - [ ] 15.8 Verify existing public reader behavior remains compatible when annotations are ignored or disabled.
  - [ ] 15.9 Verify focused backend and frontend tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Public-Safe Term Selection | 3, 10, 11, 15 |
| REQ-2 Annotation Data Shape | 2, 6, 11, 15 |
| REQ-3 Matching Terms | 5, 11, 15 |
| REQ-4 Reader Rendering | 8, 12, 15 |
| REQ-5 Controls and Configuration | 4, 9, 11, 12 |
| REQ-6 Security and Privacy | 3, 6, 10, 11, 15 |
| REQ-7 Performance and Caching | 4, 5, 7, 15 |
| REQ-8 Backward Compatibility | 6, 13, 15 |
| REQ-9 Tests | 11, 12, 14 |

## Definition of Done

- [ ] Public-safe glossary selection helper exists.
- [ ] Public chapter response includes additive `glossary_annotations`.
- [ ] Annotation matching is bounded and avoids obvious false positives.
- [ ] Frontend renders accessible highlights/tooltips without changing text.
- [ ] Reader has annotation toggle.
- [ ] Public APIs do not expose admin-only glossary data.
- [ ] Existing reader behavior remains compatible.
- [ ] Focused backend and frontend tests pass.

