# Tasks: Cloud Storage Backend (S3)

## Task List

- [x] 1. Define `StorageBackend` interface
  - [x] 1.1 Create `backend/src/novelai/storage/backends/__init__.py` (REQ-1)
  - [x] 1.2 Create `backend/src/novelai/storage/backends/base.py` with abstract `StorageBackend` class (REQ-1.1)

- [x] 2. Implement `FilesystemBackend`
  - [x] 2.1 Create `backend/src/novelai/storage/backends/filesystem.py` (REQ-2.1)
  - [x] 2.2 Implement `save` with atomic write (temp + rename) (REQ-2.4)
  - [x] 2.3 Implement `load`, `delete`, `exists`, `list_keys` (REQ-2.1)
  - [x] 2.4 Use project settings root dir (REQ-2.3)

- [x] 3. Implement `S3Backend`
  - [x] 3.1 Add `boto3` as optional dependency in `pyproject.toml` (REQ-3)
  - [x] 3.2 Create `backend/src/novelai/storage/backends/s3.py` (REQ-3.1)
  - [x] 3.3 Implement `save` via `put_object` (REQ-3.1)
  - [x] 3.4 Implement `load` via `get_object` with error handling (REQ-3.4)
  - [x] 3.5 Implement `delete`, `exists`, `list_keys` (REQ-3.1)
  - [x] 3.6 Map keys to S3 object keys with prefix (REQ-3.3)
  - [x] 3.7 Configure via settings env vars (REQ-3.2)
  - [x] 3.8 Add DEBUG logging for S3 operations (REQ-3.5)

- [x] 4. Implement factory and config validation
  - [x] 4.1 Implement `get_storage_backend()` factory in `__init__.py` (REQ-4.2)
  - [x] 4.2 Implement `_build_s3_backend()` config validation (REQ-4.3)
  - [x] 4.3 Support `STORAGE_BACKEND` setting (filesystem/s3) (REQ-4.1)
  - [x] 4.4 Cache singleton per process (REQ-4.4)

- [~] 5. Refactor existing storage consumers
  - [x] 5.1 Update `storage/service.py` — `__init__` accepts backend, uses `_backend.mkdirs` (REQ-1.3)
  - [ ] 5.2 Replace direct `open()` / `Path.read_bytes()` in sub-modules with backend calls (REQ-1.3)
  - [ ] 5.3 Verify all file paths remain identical in filesystem mode (REQ-5.1)

- [x] 6. Write tests
  - [x] 6.1 Test `FilesystemBackend` save/load/delete/exists/list_keys with `tmp_path`
  - [x] 6.2 Test atomic write prevents partial data (no .tmp files left)
  - [x] 6.3 Test `S3Backend` with moto (mock S3) — 10 tests
  - [x] 6.4 Test factory selects correct backend based on `STORAGE_BACKEND`
  - [x] 6.5 Test unknown choice raises clear error
  - [x] 6.6 Test existing tests pass with filesystem backend (REQ-5.3) — 28/28 storage backend tests pass, checkpoint resume tests pass, pre-existing failures unchanged

- [x] 7. Verify, lint, and type-check
  - [x] 7.1 Run `pytest backend/tests/test_storage_backends.py -v` — 28/28 pass
  - [x] 7.2 Run `ruff check backend/src/novelai/storage/backends/` — clean
  - [x] 7.3 Run `pyright` — 0 errors
