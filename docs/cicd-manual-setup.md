# CI/CD Manual Setup Guide

This guide covers the manual steps required to complete the CI/CD pipeline setup.
All workflow files are already implemented and committed to `.github/workflows/`.
What remains is GitHub UI configuration and verification.

---

## Prerequisites

- GitHub repository with your code pushed to `main` branch
- Admin or owner access to the repository
- A Linux/SSH-accessible server for deployment (optional, only if deploying)

---

## Task 6: Configure Repository Secrets

### Step 6.1: Add Deployment Secrets (if deploying)

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Actions**
3. Click **New repository secret** for each of the following:

| Secret Name | Value | Required |
|-------------|-------|----------|
| `DEPLOY_HOST` | Your server's IP or hostname (e.g., `123.123.123.123`) | If deploying |
| `DEPLOY_USER` | SSH username (e.g., `deploy` or `root`) | If deploying |
| `DEPLOY_SSH_KEY` | Private SSH key (PEM format) for server access | If deploying |

Generate an SSH key pair for deployment:
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f deploy_key -N ""
cat deploy_key.pub >> ~/.ssh/authorized_keys  # on your server
```

Then copy the contents of `deploy_key` into the `DEPLOY_SSH_KEY` secret.

### Step 6.2: Verify GHCR Package Permissions

The `build.yml` workflow uses `secrets.GITHUB_TOKEN` which is automatically
provided by GitHub Actions. No manual setup is needed.

Verify the repository has `packages: write` permission:

1. Go to **Settings → Actions → General**
2. Scroll to **Workflow permissions**
3. Ensure **Read and write permissions** is selected
4. Ensure **Allow GitHub Actions to create and approve pull requests** is checked

### Step 6.3: Confirm `packages: write` Permission

The `build.yml` already has `packages: write` in its `permissions` block (line 9).
No additional configuration is needed — the permission is granted at workflow level.

### Step 6.4: Configure Environment Protection Rules (if deploying)

If you want to use deployment environments (staging/production) with protection rules:

1. Go to **Settings → Environments**
2. Create environments named `staging` and `production`
3. Add **Required reviewers** if you want manual approval gates
4. Add **Wait timer** if needed

---

## Task 7: Verify Pipeline in GitHub

### Step 7.1: Push a Test PR

1. Create a new branch and push it:
   ```bash
   git checkout -b test-ci-pipeline
   # Make a minor change (e.g., add a comment)
   git add -A
   git commit -m "test: verify CI pipeline"
   git push origin test-ci-pipeline
   ```

2. Open a pull request against `main` on GitHub

3. Verify the following jobs run on the PR:
   - **backend-lint** — runs `ruff check` and `pyright`
   - **backend-tests** — runs `pytest` (without e2e)
   - **frontend-check** — runs `npm run typecheck`

4. Expected: All jobs pass with green checkmarks

### Step 7.2: Verify E2E Job Trigger

The e2e job only runs when changes affect relevant paths:

- `backend/src/novelai/services/**`
- `backend/src/novelai/api/**`
- `backend/tests/e2e/**`

To test this:
1. In your test PR, add a change to one of these paths
2. Verify the `e2e-tests` job is triggered
3. If no changes to those paths, the e2e job should be skipped (grey, not green)

### Step 7.3: Merge to Main and Verify Build

1. Merge your test PR to `main`
2. Go to **Actions** tab
3. Verify the **Build and Push** workflow is triggered on push to `main`
4. Verify Docker images are pushed to GHCR (GitHub Container Registry):
   - `ghcr.io/{owner}/{repo}/novelai-backend`
   - `ghcr.io/{owner}/{repo}/novelai-frontend`

### Step 7.4: Verify Image Tags

After a successful build, check that images are tagged with:
- **SHA tag:** `sha-{commit_sha}` (e.g., `sha-a1b2c3d4`)
- **Latest tag:** `latest`

You can verify in the GitHub UI:
1. Go to your repository main page
2. Click the **Packages** tab
3. Click on each package
4. Verify both tags exist

### Step 7.5: Verify CI Completion Time

The CI pipeline should complete in under 5 minutes on a cache-hit run:

- **Cache-hit on pip:** < 30s for Python deps
- **Cache-hit on npm:** < 30s for Node deps
- **Docker BuildKit GHA cache:** < 2min for cached layers

Check the Actions run duration. If it exceeds 5 minutes:
- Verify pip/npm caching is working (look for "cache hit" in logs)
- Verify Docker BuildKit GHA cache is working
- Split the build into separate jobs if needed

### Step 7.6: Run Manual Deploy Workflow

After secrets are configured (Task 6):

1. Go to **Actions → Deploy → Run workflow**
2. Select the `version` tag (e.g., `latest` or a specific SHA)
3. Select the environment (`staging` or `production`)
4. Click **Run workflow**
5. Verify the deploy script executes successfully on your server

Expected output on your server:
```bash
cd /opt/novelai
docker compose pull
docker compose up -d --remove-orphans
```

---

## Verification Checklist

- [ ] PR CI runs backend-lint, backend-tests, frontend-check
- [ ] E2E tests run when relevant paths change
- [ ] Merge to main triggers Docker build and push
- [ ] Docker images pushed to GHCR with SHA and `latest` tags
- [ ] CI completes in under 5 minutes on cache-hit
- [ ] (Optional) Deploy workflow runs successfully

---

## Common Issues

| Issue | Fix |
|-------|-----|
| `permission denied` on GHCR push | Verify `packages: write` in Settings → Actions → Workflow permissions |
| `DEPLOY_HOST` secret missing | Add secret in Settings → Secrets and variables → Actions |
| E2E tests don't run on PR | Check path filter in `ci.yml` — only runs on `backend/src/novelai/services/**`, `backend/src/novelai/api/**`, `backend/tests/e2e/**` |
| Build images missing `latest` tag | Verify `docker/metadata-action` config in `build.yml` |
| Deploy fails with `Host key verification` | Add the host to `known_hosts` or use `-o StrictHostKeyChecking=no` in the SSH action |
| Frontend Docker build fails | Ensure `frontend/Dockerfile` exists and uses Next.js standalone output |
