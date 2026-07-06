# Tasks: Glossary Management Consolidation

## Task List

- [ ] 1. Inventory glossary paths
  - [ ] 1.1 Locate global glossary storage and novel-scoped glossary storage (REQ-1.1)
  - [ ] 1.2 Locate prompt builder glossary inputs (REQ-4.1)
  - [ ] 1.3 Locate admin glossary API/UI routes (REQ-3.1)

- [ ] 2. Implement resolver
  - [ ] 2.1 Add global + novel approved-term loader (REQ-1.1)
  - [ ] 2.2 Apply novel-over-global override rule (REQ-1.2)
  - [ ] 2.3 Exclude candidate/rejected entries (REQ-1.3)
  - [ ] 2.4 Generate deterministic `glossary_hash` (REQ-1.4)

- [ ] 3. Enforce lifecycle metadata
  - [ ] 3.1 Ensure entries expose scope/status fields (REQ-2.1, REQ-2.3)
  - [ ] 3.2 Ensure novel entries require `novel_id` (REQ-2.2)
  - [ ] 3.3 Ensure owner-only mutations (REQ-2.4)

- [ ] 4. Integrate translation
  - [ ] 4.1 Pass resolved glossary into prompt builders (REQ-4.1)
  - [ ] 4.2 Include `glossary_hash` in translation cache key (REQ-4.2)
  - [ ] 4.3 Record hash/version in provider request metadata (REQ-4.3)

- [ ] 5. Align admin UI
  - [ ] 5.1 Show backend-provided conflict/status fields (REQ-3.1)
  - [ ] 5.2 Remove client-side merge policy if present (REQ-3.2)

- [ ] 6. Verify
  - [ ] 6.1 Test global-only, novel-only, novel override cases (REQ-5.1)
  - [ ] 6.2 Test candidate/rejected exclusion (REQ-5.2)
  - [ ] 6.3 Test owner-only glossary mutations (REQ-5.3)