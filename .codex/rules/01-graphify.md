# Graphify

Knowledge graph at `graphify-out/graph.json`. Uses `nodes`, `links`, `hyperedges`
keys; each node has `source_file`, `source_location`, `file_type`, `_origin`.

Distribution: PyPI/uv package `graphifyy`, CLI `graphify`, current version **0.9.28**.
Isolated uv tool install: `uv tool install "graphifyy[sql,gemini]==0.9.28"`.
`tree-sitter-sql` extra available as `graphifyy[sql]` (v0.3.11).

## CLI Commands

| Context | Command | Notes |
|---------|---------|-------|
| **Local / CI (no API key)** | `graphify update . --no-cluster` | AST-only re-extraction, no LLM call across source + SQL |
| Query | `graphify query "<question>"` | Requires API key + semantic graph |
| Path | `graphify path "<A>" "<B>"` | Requires API key + semantic graph |
| Explain | `graphify explain "<concept>"` | Requires API key + semantic graph |
| Semantic extraction | `graphify extract` (or `graphify update .` with key set) | Operator-only. See API Keys section below for rate-safe invocation. |

After `graphify update . --no-cluster`, only `graphify-out/graph.json` and live CLI
queries (`graphify query`/`path`/`explain`) are authoritative.
MCP tools that read the graph depend on the same JSON — no special reload
environment variable exists. A restart or new MCP session may be needed depending
on the harness; verify by running a CLI query after refresh.

`.graphify_analysis.json`, `.graphify_labels.json`, `GRAPH_REPORT.md`, wiki, and
community prose may remain from the last clustering/labeling milestone and must NOT
be cited as current unless explicitly refreshed. Do not invoke LLM re-clustering
for routine source edits.

**Semantic extraction can omit prose symbol nodes.** Rely on manifest scan plus
hyperedges/document evidence for documentation coverage. When doing milestone
verification, check code/SQL changed-file coverage through `source_file` in
the graph, not through prose or community labels.

**Dated evidence from last full semantic milestone (2026-07-27):**
The dated milestone proves the rebuild completed but is **not** a graph invariant.
Counts change after every extraction, update, or reclustering. Use the live CLI
or `graphify-out/graph.json` for current node/link/hyperedge/community counts;
treat any number cited here as stale unless re-verified on demand.

## Verification

Normal checks:

1. Run `graphify update . --no-cluster` and check exit code + warnings.
2. Verify `graphify-out/graph.json` has non-zero nodes and expected `source_file` entries.
3. Check zero-node warnings (see Zero-Node Policy below).
4. For changed `.py`/`.ts`/`.tsx`/`.sql` files, confirm they appear in graph `source_file` records.
5. Confirm `backend/sql/*.sql` files produce non-zero nodes in graph.
6. Use `git status`, lint, type checks, and focused tests for quality validation.

## API Keys (Semantic Extraction)

Required only for `graphify extract` or `graphify update .` with a Gemini backend.
Set these environment variables **before** running the command:

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Primary Gemini API key (process env only) |
| `GOOGLE_API_KEY` | Fallback Gemini API key (same value) |
| `GRAPHIFY_GEMINI_MODEL` | Optional model override (e.g. `gemini-2.0-flash-lite`) |

**Rate-safe first invocation:**
```powershell
$env:GEMINI_API_KEY = "<your-key>"
graphify extract --max-concurrency 1 --api-timeout 120 --token-budget 800000
```
Adjust concurrency, timeout, and budget only after observing provider rate limits.
Do not hardcode the example values as universal — limits vary by provider and plan.

**Security rules:**
- Never write API keys into any file inside the repository — no `.env` committed,
  no tracked config, no embedded-key script, no command-line arg, no log output.
- Set keys via `$env:GEMINI_API_KEY = "..."` in **process scope only** (lasts
  until the PowerShell window closes).
- For CI, use the platform's secret store (GitHub Actions secrets etc.); never
  paste keys in workflow YAML.
- If a key is exposed (logged, committed, pasted), rotate it immediately.
- A leaked Gemini key can incur unexpected billing.
- Do not paste, print, log, or return API key values in any output.

## tree_sitter_sql Installation

Graphify uses `tree-sitter-sql` (v0.3.11) to parse `.sql` files. If SQL files
produce zero nodes, ensure the `sql` extra is installed:

```powershell
# uv tool (pinned)
uv tool install "graphifyy[sql]==0.9.28"

# pip (any Python environment)
python -m pip install graphifyy[sql]
```

After install, verify SQL parsing: run `graphify update . --no-cluster` and
check that `backend/sql/*.sql` files produce non-zero nodes.

## Zero-Node Policy

Graphify may report files that produce zero AST nodes. Four known benign files
are declarative JSON configs the AST parser cannot process. Any OTHER zero-node
file is a FAILURE — investigate:

- `.codex/hooks.json` — Codex pre-tool-use hooks (pure JSON config)
- `.vscode/extensions.json` — VS Code extension recommendations
- `.vscode/settings.json` — VS Code workspace settings
- `pyrightconfig.json` — Pyright type checker configuration

**ponytail:** Graphify has no JSON parser for semantic extraction. Reevaluate or
remove this allowlist when Graphify adds generic JSON semantic extraction, or
when warning format/path behavior changes. Until then, any unexpected zero-node
file continues to be a FAILURE.

## Pre-commit Hook

The `.codex/hooks.json` pre-tool-use hook runs `graphify hook-check` before
every Bash tool execution to verify the graph is not stale.

The git post-commit hook rebuilds the graph automatically after commits:
`graphify hook install` sets this up. If no hook is installed, run
`graphify update . --no-cluster` manually after relevant changes.

Do not commit `graphify-out/` files — they are gitignored.

## Installation & Updates

Current verified version: **0.9.28**.

```powershell
# Fresh install (pinned, with all extras)
uv tool install "graphifyy[sql,gemini]==0.9.28"

# Upgrade to latest
uv tool upgrade graphifyy

# Verify
graphify --version
```

To add the `sql` extra to an existing install:
```powershell
uv tool install "graphifyy[sql]==0.9.28" --reinstall
```

`tree-sitter-sql` v0.3.11 is bundled via the `[sql]` extra. Verify SQL parsing
by running `graphify update . --no-cluster` and checking `backend/sql/` files.
