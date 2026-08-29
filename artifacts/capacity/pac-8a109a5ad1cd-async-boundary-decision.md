# Async boundary decision

Decision: choose design Option B, a bounded synchronous persistence/storage
executor exposed through an async-facing port. The first slice is reversible
and preserves the current SQLAlchemy and S3/R2 implementations; a fully
async-native adapter remains a later option only if measurements justify it.

## Contract

- The coordinator passes immutable scalar/DTO commands only: canonical ids,
  hashes, exact artifact references, bounded state, and deterministic
  idempotency keys.
- The executor creates or acquires a session inside each operation, performs
  one short transaction, commits or rolls back, closes it, and returns a
  plain result DTO.
- R2 clients are owned by the operation boundary or explicitly proven safe;
  no mutable client is assumed thread-safe because a test double is safe.
- Provider calls, retry sleeps, and QA waits remain outside the persistence
  executor and do not hold a database connection.
- Terminal artifact/reference/state writes use a critical atomic command;
  safe progress/events use bounded coalescing and replay rules.

## Admission and rollback

- Executor workers are fixed and bounded by the worker's admitted DB write
  slots and the deployment-wide `DB_CONNECTION_BUDGET` arithmetic.
- Submission uses a bounded queue. Critical commands wait with a deadline;
  non-critical progress is coalesced or rejected with an observation rather
  than allocated into an unbounded task list.
- Queue wait, operation duration, rows, commit, R2 operation counts, bytes,
  and failure codes use the versioned telemetry contract.
- Cancellation stops new work, lets an already-running short transaction
  settle, reconciles its idempotency key, and releases the executor slot.
- Shutdown stops admission, drains critical commands to a fixed deadline,
  records a checkpoint, and keeps the worker stopped if the deadline fails.
- Rollback is the disabled boundary/feature gate and return to the prior
  bounded activity path; no schema migration, bucket cutover, provider-plan
  change, or full-queue restart is part of this decision.

## Rejection criteria

Reject or pause this slice if tests or bounded evidence show live session/ORM
crossing, lazy loads after close, a database connection held across provider,
R2, retry, or QA waits, unbounded task/queue growth, false terminal state,
duplicate immutable references, lease loss, or resource telemetry that cannot
be redacted/provenanced.
