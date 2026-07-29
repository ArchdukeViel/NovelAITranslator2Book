# Maintenance Runtime Status Design

`SchedulerService` and `MaintenanceService` keep execution policy. Add one service
projection reading registered jobs plus `SchedulerRuntimeStateService`; router
remains thin. Frontend uses `frontend/lib/api.ts` and TanStack Query.

Response uses canonical task key, schedule, timezone, runtime status, timestamps,
next eligibility, and redacted message. Missing state is `never_run`, not success.
Any normal-operation cache/DB mismatch reports degraded and prefers DB truth.
