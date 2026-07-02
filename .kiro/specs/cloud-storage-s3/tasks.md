# Tasks: Cloud Storage Backend (S3)

## Task List

- [ ] 1. Define `StorageBackend` interface
  - [ ] 1.1 Create `backend/src/novelai/storage/backends/__init__.py` (REQ-1)
  - [ ] 1.2 Create `backend/src/novelai/storage/backends/base.py` with abstract `StorageBackend` class (REQ-1.1)

- [ ] 2. Implement `FilesystemBackend`
  - [ ] 2.1 Create `backend/src/novelai/storage/backends/filesystem.py` (REQ-2.1)
  - [ ] 2.2 Implement `save` with atomic write (temp + rename) (REQ-2.4)
  - [ ] 2.3 Implement `load`, `delete`, `exists`, `list_keys` (REQ-2.1)
  - [ ] 2.4 Use `STORAGE_PATH` env var for root directory (REQ-2.3)

- [ ] 3. Implement `S3Backend`
  - [ ] 3.1 Add `boto3` as optional dependency in `pyproject.toml` (REQ-3)
  - [ ] 3.2 Create `backend/src/novelai/storage/backends/s3.py` (REQ-3.1)
  - [ ] 3.3 Implement `save` via `put_object` (REQ-3.1)
  - [ ] 3.4 Implement `load` via `get_object` with error handling (REQ-3.4)
  - [ ] 3.5 Implement `delete`, `exists`, `list_keys` (REQ-3.1)
  - [ ] 3.6 Map keys to S3 object keys with prefix (REQ-3.3)
  - [ ] 3.7 Configure via env vars (REQ-3.2)
  - [ ] 3.8 Add DEBUG logging for S3 operations (REQ-3.5)

- [ ] 4. Implement factory and config validation
  - [ ] 4.1 Implement `get_storage_backend()` factory in `__init__.py` (REQ-4.2)
  - [ ] 4.2 Implement `_validate_s3_config()` startup check (REQ-4.3)
  - [ ] 4.3 Support `STORAGE_BACKEND` env var (filesystem/s3) (REQ-4.1)
  - [ ] 4.4 Cache singleton per process (REQ-4.4)

- [ ] 5. Refactor existing storage consumers
  - [ ] 5.1 Update `storage/service.py` to use `get_storage_backend()` (REQ-1.3)
  - [ ] 5.2 Replace direct `open()` / `Path.read_bytes()` with backend calls (REQ-1.3)
  - [ ] 5.3 Verify all file paths remain identical in filesystem mode (REQ-5.1)

- [ ] 6. Write tests
  - [ ] 6.1 Test `FilesystemBackend` save/load/delete/exists/list_keys with `tmp_path`
  - [ ] 6.2 Test atomic write prevents partial data on crash simulation
  - [ ] 6.3 Test `S3Backend` with moto or localstack (mock S3)
  - [ ] 6.4 Test factory selects correct backend based on `STORAGE_BACKEND`
  - [ ] 6.5 Test startup fails with clear error when S3 config is missing
  - [ ] 6.6 Test existing tests pass with filesystem backend (REQ-5.3)

- [ ] 7. Verify, lint, and type-check
  - [ ] 7.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [ ] 7.2 Run `ruff check backend/src/novelai/storage/backends/` and fix issues
  - [ ] 7.3 Run `pyright` and fix type errors
