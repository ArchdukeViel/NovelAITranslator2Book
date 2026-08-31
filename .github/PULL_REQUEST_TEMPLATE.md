## Summary

<!-- What does this PR do and why? -->

## Change type

- [ ] fix
- [ ] feat
- [ ] refactor
- [ ] docs
- [ ] test
- [ ] chore

## Test plan

<!-- Exact commands run and results. Prefer tools/ wrappers:
  & tools/pytest.ps1 <focused file>
  & tools/ruff.ps1 check backend/src backend/tests
  & tools/pyright.ps1
-->

## Contract checks

- [ ] Stable chapter ids are never converted with `int(chapter["id"])` or
      `chapter_id.isdigit()`.
- [ ] Translation writes go through the overlay
      (`translations/<encoded-stem>.json`), never a committed raw generation.
- [ ] Generation activation only via `commit_generation` after validation.
- [ ] No secrets, credential fragments, `.env`, or DB URLs in the diff.
- [ ] `uv.lock` regenerated when dependencies changed.

## Docs

- [ ] `docs/` updated when behavior, storage, config, or deployment changed.
- [ ] `docs/EVIDENCE.md` updated when work is completed.
