# Shared Rules and Standards

Authoritative system instructions live in `AGENTS.md` and `.agents/rules/`. All Codex sessions must observe these rules:

1. **Architecture & Truth**: Follow `docs/ARCHITECTURE.md` as supreme contract.
2. **Environment & Tooling**: Never run bare `python`/`pytest`/`ruff`. Use `tools/pytest.ps1`, `tools/pyright.ps1`, `tools/ruff.ps1`.
3. **Graph Intelligence**: For architecture questions, query `graphify-out/graph.json` via `graphify query "<question>"`. Run `graphify update . --no-cluster` after edits.
4. **Security & Secrets**: Never read or log `.env` files, connection strings, or raw tokens.
5. **Storage Invariants**: Chapter IDs are stable strings; generation artifacts are byte-immutable; writes go to translation overlay.
6. **Workflow & Verification**: Run focused tests before broad suites. Adhere to plan-first directives unless trivial single-line change.
