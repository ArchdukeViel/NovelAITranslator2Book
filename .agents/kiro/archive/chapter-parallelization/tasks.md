# Tasks: Chapter Parallelization

## Task List

- [x] 1. Inspect current orchestration
  - [x] 1.1 Locate chapter loop in orchestration/translation service (REQ-1.4)
  - [x] 1.2 Identify activity progress update points (REQ-3.3)
  - [x] 1.3 Identify provider scheduler call boundary (REQ-3.1)

- [x] 2. Add concurrency setting
  - [x] 2.1 Add backend-owned max parallel chapters setting/profile value (REQ-1.2)
  - [x] 2.2 Default setting to `1` (REQ-1.1)
  - [x] 2.3 Validate setting bounds server-side (REQ-1.3)

- [x] 3. Add bounded executor
  - [x] 3.1 Wrap chapter processing in bounded async/thread executor (REQ-1.1)
  - [x] 3.2 Keep chunk pipeline unchanged inside each chapter task (REQ-3.1)
  - [x] 3.3 Respect scheduler pause/cooldown responses (REQ-3.2)

- [x] 4. Preserve state and output order
  - [x] 4.1 Write outputs per chapter through storage service (REQ-2.2)
  - [x] 4.2 Collect results by source chapter index (REQ-2.1)
  - [x] 4.3 Ensure failed chapter does not delete successful outputs (REQ-2.4)
  - [x] 4.4 Keep retry state scoped to failed chapter/chunks (REQ-2.3)

- [x] 5. Add progress reporting
  - [x] 5.1 Emit running/succeeded/failed per-chapter states (REQ-3.3)
  - [x] 5.2 Include partial-failure summary in activity output (REQ-3.3)

- [x] 6. Verify
  - [x] 6.1 Test concurrent fake-provider execution (REQ-4.1)
  - [x] 6.2 Test stable output order (REQ-4.2)
  - [x] 6.3 Test one chapter failure preserves other outputs (REQ-4.3)
  - [x] 6.4 Test concurrency `1` equals sequential behavior (REQ-4.4)