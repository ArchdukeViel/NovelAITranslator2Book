# GitHub Repository Controls

## Live owner-operated settings

These must be configured through the GitHub UI or API. No in-code representation exists.

### Branch protection — `main` ruleset

| Setting | Value |
|---------|-------|
| Ruleset name | `protect-main` |
| Target branch | `main` |
| Enforcement status | Active |
| **Require a pull request before merging** | Enabled |
| Required approvals | 1 |
| Dismiss stale pull request approvals when new commits are pushed | Enabled |
| Require review from Code Owners | Enabled |
| **Require status checks** | Enabled |
| Required status checks | `backend-lint`, `backend-tests`, `backend-extended-tests`, `frontend-checks`, `docker-build` |
| Require branches to be up to date before merging | Enabled |
| **Require merge queue** | Disabled (consider enabling when contributor count grows) |
| **Restrict deletions** | Enabled |
| **Block force pushes** | Enabled |
| Bypass list | Owner only |

### Actions permissions — general

| Setting | Value |
|---------|-------|
| **Actions permissions** | `Allow OWNER, and select non-OWNER, actions and reusable workflows` |
| Allow actions | Only pinned actions listed below |
| **Fork pull request workflows** | `Disable — don't run workflows from fork pull requests` |

Allowlist (pinned actions, SHA-pinned in workflows):

- `actions/checkout`
- `actions/setup-python`
- `actions/upload-artifact`
- `actions/download-artifact`
- `docker/setup-buildx-action`
- `docker/login-action`
- `docker/metadata-action`
- `docker/build-push-action`
- `azure/setup-helm`

### Dependabot

| Setting | Status |
|---------|--------|
| Dependabot security updates | Enabled |
| Dependabot version updates | Not configured (manual review preferred) |
| Dependabot secret scanning alerts | Enabled |

### Secret scanning

| Setting | Status |
|---------|--------|
| Secret scanning | Enabled |
| Push protection | Enabled |
| Validity checks | Enabled |

### CodeQL

| Setting | Status |
|---------|--------|
| CodeQL analysis | Enabled — default setup (scheduled: daily) |
| Scan on push | Enabled for `main` |
| Language | Python, JavaScript/TypeScript |
| Query suites | `security-and-quality` |

### Other security

| Setting | Status |
|---------|--------|
| Private vulnerability reporting | Enabled |
| Automatic security updates | Enabled |

---

## In-code tracked configuration

These are version-controlled in `.github/workflows/`. Changes go through the standard PR + review process.

### Workflow files

| File | Trigger | Purpose |
|------|---------|---------|
| `.github/workflows/ci.yml` | Push/PR to `main`, `develop` | Backend lint, tests (sharded), frontend checks, router-layer violation check |
| `.github/workflows/build.yml` | CI success on `main` | Build & push Docker images to GHCR (SHA-pinned + `latest`) |
| `.github/workflows/deploy.yml` | `workflow_dispatch` or tag `v*` | Deploy to staging/production environments |
| `.github/workflows/managed-services-verification.yml` | Scheduled | Verify managed service connectivity |
| `.github/workflows/opencode.yml` | PR comments | OpenCode assistant integration |

### SHA pinning status

Per DEBT-078 implementation note (2026-07-22): all third-party actions in tracked workflows are pinned to immutable commit SHAs with comments indicating the semantic version. Review periodically on version bumps.

Write permissions are scoped per job — the narrowest set required. `permissions: {}` at workflow top level (no default token for `build.yml`); individual jobs escalate only as needed.

### Dependabot configuration

If dependabot version updates are needed in the future, add `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "weekly"
```

---

## Gap note

`docs/cicd-manual-setup.md` is referenced by `AGENTS.md` and by DEBT-078 but does not yet exist. When created, it should contain the one-time GitHub UI setup steps (branch protection, Actions permissions, secret scanning, CodeQL) and environment/secret configuration. See `docs/operations/github-controls.md` for the canonical settings reference.
