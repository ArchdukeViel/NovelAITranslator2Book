# Tasks: Semantic Cache and LLM QA Roadmap

## Task List

- [ ] 1. Complete prerequisites
  - [ ] 1.1 Ship exact translation memory metrics (REQ-1.1)
  - [x] 1.2 Ship deterministic QA checks and parser tests (REQ-3.1)

- [ ] 2. Build evaluation fixtures
  - [x] 2.1 Create accepted fuzzy-match examples (REQ-1.2)
  - [x] 2.2 Create rejected fuzzy-match examples where context changes meaning (REQ-1.2)
  - [x] 2.3 Define precision threshold for enabling reuse (REQ-1.4)

- [ ] 3. Design semantic cache storage
  - [ ] 3.1 Choose embedding/index backend after fixture size is known (REQ-2.2)
  - [ ] 3.2 Define idempotent index write contract (REQ-2.3)
  - [ ] 3.3 Define provider credential isolation (REQ-2.1)

- [ ] 4. Design LLM QA output
  - [ ] 4.1 Define structured finding schema with severity/evidence (REQ-3.2)
  - [x] 4.2 Add parser tests for valid/invalid output (REQ-4.2)
  - [ ] 4.3 Keep initial behavior review-flag only (REQ-3.3)

- [ ] 5. Add disabled-by-default config checks
  - [x] 5.1 Test semantic cache disabled by default (REQ-4.3)
  - [x] 5.2 Test LLM QA disabled by default (REQ-4.3)