# Tasks: Storage Boundary Consolidation

## Task List

- [x] 1. Inventory storage access
  - [x] 1.1 Search backend for direct filesystem access to runtime storage (REQ-2.1)
  - [x] 1.2 Classify results as canonical, test, compatibility, or violation (REQ-2.1)

- [x] 2. Define minimal chapter content gateway
  - [x] 2.1 Add or confirm canonical raw chapter read/write methods (REQ-1.2)
  - [x] 2.2 Add or confirm canonical translated chapter read/write methods (REQ-1.2)
  - [x] 2.3 Preserve `novel_id` and `chapter_id` in returned content objects (REQ-3.1)

- [x] 3. Remove boundary violations
  - [x] 3.1 Replace router-level direct path access with service/storage calls (REQ-2.2)
  - [x] 3.2 Replace service-level direct path access where behavior is clear (REQ-2.3)
  - [x] 3.3 Leave explicit compatibility comments where legacy reads must remain (REQ-2.3)

- [x] 4. Add safety tests
  - [x] 4.1 Test legacy content read-through via storage service (REQ-4.1)
  - [x] 4.2 Test public/admin APIs do not expose absolute paths or `storage/novel_library` (REQ-4.2)
  - [x] 4.3 Test corrupt/missing content returns safe error envelope (REQ-4.3)

- [x] 5. Verify
  - [x] 5.1 Run `pytest --tb=short -q` for storage/API tests
  - [x] 5.2 Run `ruff check .`