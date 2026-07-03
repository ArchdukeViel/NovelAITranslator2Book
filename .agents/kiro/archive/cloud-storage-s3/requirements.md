# Requirements: Cloud Storage Backend (S3)

## Introduction

All chapter content is stored on the local filesystem under `storage/novel_library/`. While convenient for development, this approach limits scalability, complicates backups, and makes deployment across multiple instances difficult (each instance has its own filesystem). There is no abstraction layer between the storage consumer and the filesystem, meaning every file read/write is a direct `open()` call.

This spec introduces a pluggable storage backend abstraction with filesystem and S3-compatible implementations, configurable via a `STORAGE_BACKEND` environment variable. The existing filesystem backend remains the default.

## Requirements

### REQ-1: Storage Backend Interface

A canonical storage interface must be defined.

- REQ-1.1: Define an abstract base class `StorageBackend` in `backend/src/novelai/storage/backends/base.py` with async methods:
  - `async save(key: str, data: bytes | str) -> None`
  - `async load(key: str) -> bytes`
  - `async delete(key: str) -> None`
  - `async exists(key: str) -> bool`
  - `async list_keys(prefix: str = "") -> list[str]`
- REQ-1.2: The interface must be async-first (all methods return awaitables) to support network I/O for S3.
- REQ-1.3: All existing storage operations must be refactored to use the `StorageBackend` interface instead of direct file I/O.

### REQ-2: Filesystem Backend

The existing filesystem storage must be wrapped as a backend implementation.

- REQ-2.1: Implement `FilesystemBackend` in `backend/src/novelai/storage/backends/filesystem.py` conforming to the `StorageBackend` interface.
- REQ-2.2: The filesystem backend must use the existing `storage/novel_library/` directory structure and file naming conventions. No file layout changes.
- REQ-2.3: The filesystem backend must support the `STORAGE_PATH` environment variable (default: `storage/novel_library`).
- REQ-2.4: File writes must be atomic (write to temp file, then rename) to prevent partial writes from corrupting storage.

### REQ-3: S3 Backend

An S3-compatible backend must be implemented.

- REQ-3.1: Implement `S3Backend` in `backend/src/novelai/storage/backends/s3.py` using the `boto3` library.
- REQ-3.2: The S3 backend must support configuration via environment variables:
  - `S3_ENDPOINT_URL` — custom endpoint (for MinIO, DigitalOcean Spaces, etc.)
  - `S3_BUCKET` — bucket name
  - `S3_ACCESS_KEY_ID` — access key
  - `S3_SECRET_ACCESS_KEY` — secret key
  - `S3_REGION` — region (default: `us-east-1`)
  - `S3_PREFIX` — key prefix within bucket (default: `novel_library/`)
- REQ-3.3: The S3 backend must map `key` to S3 object keys as `{S3_PREFIX}/{key}`.
- REQ-3.4: The S3 backend must handle connection errors gracefully: retry up to 3 times with exponential backoff (1s, 2s, 4s) on transient errors.
- REQ-3.5: S3 operations must log at DEBUG level: `"s3: PUT {bucket}/{key} (N bytes)"`.

### REQ-4: Backend Selection

The storage backend must be selectable at startup.

- REQ-4.1: A `STORAGE_BACKEND` environment variable must control backend selection. Valid values: `"filesystem"` (default), `"s3"`.
- REQ-4.2: A factory function `get_storage_backend() -> StorageBackend` must instantiate and return the configured backend.
- REQ-4.3: The S3 backend must validate its configuration at startup: if `STORAGE_BACKEND=s3` but required env vars are missing, the application must refuse to start with a clear error.
- REQ-4.4: The backend selection must be cached (singleton per process) to avoid creating multiple S3 client instances.

### REQ-5: Migration Compatibility

Existing storage must remain accessible.

- REQ-5.1: When using the filesystem backend, all existing file paths and directory structures must remain identical.
- REQ-5.2: A `STAGE` env var (default: `development`) must control whether storage warnings about missing directories are silenced in production (S3 mode).
- REQ-5.3: Existing tests that use the filesystem must continue to pass without modification.

## Non-Goals

- This spec does not add a data migration tool from filesystem to S3 (that is a separate operational task).
- This spec does not add a hybrid/cached backend (filesystem cache in front of S3).
- This spec does not add Azure Blob or GCP Cloud Storage backends (S3 protocol covers most providers).
- This spec does not change the file format or naming conventions of stored data.
