# Tasks: Exact Translation Memory

## Task List

- [x] 1. Locate translation provider call boundary
  - [x] 1.1 Identify current chunk-to-provider flow in `translation/` and `services/` (REQ-1.1)
  - [x] 1.2 Identify existing translation cache models/repositories, if any (REQ-1.1)

- [x] 2. Add cache key builder
  - [x] 2.1 Build deterministic source text hash (REQ-2.1)
  - [x] 2.2 Include language, prompt version, provider key/model, and glossary hash fields (REQ-2.2)
  - [x] 2.3 Add unit tests for key stability and key separation (REQ-2.1, REQ-2.2)

- [x] 3. Add cache repository methods
  - [x] 3.1 Implement `get` for cache lookup (REQ-1.2)
  - [x] 3.2 Implement `put` for successful outputs only (REQ-1.3, REQ-1.4)
  - [x] 3.3 Ensure stored metadata excludes secrets (REQ-2.3)

- [x] 4. Integrate cache into translation flow
  - [x] 4.1 Lookup before provider call (REQ-1.1)
  - [x] 4.2 Skip provider request records on cache hit (REQ-3.3)
  - [x] 4.3 Save output only after QA pass (REQ-1.4)

- [x] 5. Add observability
  - [x] 5.1 Emit activity cache hit/miss counters (REQ-3.1)
  - [x] 5.2 Log hit/miss with key prefix only (REQ-3.2)

- [x] 6. Verify
  - [x] 6.1 Test duplicate source calls provider once (REQ-4.1)
  - [x] 6.2 Test prompt/glossary changes miss cache (REQ-4.2)
  - [x] 6.3 Test rejected output is not cached (REQ-4.3)
  - [x] 6.4 Run targeted pytest and `ruff check .`