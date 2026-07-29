# Maintenance Runtime Status Requirements

## Goal

Give owner one truthful maintenance status view backed by durable scheduler state.

## Requirements

1. List every registered maintenance task with schedule and timezone.
2. Show last start/completion, result, safe failure summary, and next eligible run.
3. Use `SchedulerRuntimeState` as durable truth; cache may accelerate but not contradict it.
4. Owner-only API/UI; public output and logs remain redacted.
5. Preserve dry-run and path-safety behavior.
6. Prove restart persistence, multi-process lease behavior, and cache/DB reconciliation.

## Out of Scope

New cleanup tasks, APScheduler, arbitrary operator paths, and public status access.
