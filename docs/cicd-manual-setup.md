# CI/CD Manual Setup

One-time GitHub repository configuration steps. Run these after repository creation and before the first CI run.

---

## Prerequisites

- GitHub account with Admin access to the repository
- GitHub CLI (`gh`) or browser access to Settings

---

## Branch protection — `main`

Create a ruleset via Settings > Rules > Rulesets > New ruleset:

1. Name: `protect-main`
2. Target: `main`
3. Enforcement: Active
4. Enable: Require a pull request before merging
   - Required approvals: 1
   - Dismiss stale approvals: Yes
   - Require review from Code Owners: Yes
5. Enable: Require status checks
   - Add: `backend-lint`, `backend-tests`, `backend-extended-tests`, `frontend-checks`, `docker-build`
   - Require branches to be up to date: Yes
6. Enable: Restrict deletions
7. Enable: Block force pushes
8. Bypass list: Owner only

Reference: `docs/operations/github-controls.md` — Branch protection section.

---

## Actions permissions

Settings > Actions > General:

1. **Allow OWNER, and select non-OWNER, actions and reusable workflows**
   - Allow actions: select the allowlist in `docs/operations/github-controls.md`
2. **Fork pull request workflows:** Disable (don't run workflows from forks)

Reference: `docs/operations/github-controls.md` — Actions permissions section.

---

## Actions secrets and variables

Settings > Secrets and variables > Actions:

### Secrets

| Name | Value | Notes |
|------|-------|-------|
| `GHCR_PAT` | GitHub PAT with `packages:write`, `contents:read` | Used in build.yml for registry login |
| `DOCKER_BUILD_CACHE_SCOPE` | `novelai` | GHA cache scope for Docker builds |
| `STAGING_SSH_KEY` | SSH private key for staging host | Deploy target |
| `PRODUCTION_SSH_KEY` | SSH private key for production host | Deploy target |

Add deployment-specific secrets (database URLs, provider keys, etc.) as GitHub Environments variables/secrets (see next section).

### Variables

| Name | Value | Notes |
|------|-------|-------|
| `CONTAINER_REGISTRY` | `ghcr.io` | |
| `CONTAINER_REPO` | `ghcr.io/<owner>/<repo>` | Lowercase |

---

## Environments

Settings > Environments:

### `staging`

| Setting | Value |
|---------|-------|
| Required reviewers | (optional) |
| Wait timer | 0 |
| Deployment branches | `main` |
| Environment secrets | `DATABASE_URL`, `SESSION_SECRET_KEY`, `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`, `WEB_CORS_ORIGINS`, `PUBLIC_FRONTEND_URL` |

### `production`

| Setting | Value |
|---------|-------|
| Required reviewers | Owner |
| Wait timer | 0 |
| Deployment branches | `main` (tagged `v*`) |
| Environment secrets | `DATABASE_URL`, `SESSION_SECRET_KEY`, `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`, `WEB_CORS_ORIGINS`, `PUBLIC_FRONTEND_URL`, `OWNER_BOOTSTRAP_SECRET` |

---

## Secret scanning

Settings > Code security > Secret scanning:

1. Enable Secret scanning
2. Enable Push protection
3. Enable Validity checks

---

## CodeQL

Settings > Code security > CodeQL:

1. Enable CodeQL analysis — default setup
2. Languages: Python, JavaScript/TypeScript
3. Schedule: Daily
4. Query suite: `security-and-quality`

---

## Dependabot

Settings > Code security > Dependabot:

1. Enable Dependabot security updates
2. Enable Dependabot secret scanning alerts

If dependabot version updates are desired later, add `.github/dependabot.yml` per the template in `docs/operations/github-controls.md`.

---

## Verification checklist

After setup:

- [ ] Push to `main` without a PR — rejected
- [ ] Push a PR with failing status checks — blocked from merge
- [ ] Fork PR — Actions do not run
- [ ] Push a commit containing a dummy credential — push protection blocks it
- [ ] CodeQL analysis completes on next push/schedule

---

## Related documents

- `docs/operations/github-controls.md` — full settings reference and in-code vs owner-operated split
- `docs/operations/deployment.md` — container layout, routing, deployment architecture
