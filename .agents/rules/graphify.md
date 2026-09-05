---
trigger: always_on
description: Consult the graphify knowledge graph at graphify-out/ for codebase and architecture questions, and update after code modifications.
---

# Graphify Knowledge Graph

This project maintains a synchronized Graphify knowledge graph under `graphify-out/`.

## Code Intelligence & Architecture Queries

- **Graph-First Navigation**: When `graphify-out/graph.json` exists, reach for Graphify before broad raw grep:
  - Scoped concept questions: `graphify query "<question>"` (CLI) or `query_graph` (MCP).
  - Cross-artifact relationships: `graphify path "<SymbolA>" "<SymbolB>"` / `shortest_path`.
  - Focused definitions: `graphify explain "<concept>"` / `get_node`.
- **Navigating Wiki**: If `graphify-out/wiki/index.md` exists, consult it for subsystem maps before reading raw source trees.
- **Architecture Summaries**: Read `graphify-out/GRAPH_REPORT.md` only for broad high-level review when scoped queries do not surface sufficient context.

## Refresh & Synchronization Contract

- **Post-Edit AST Refresh**: After completing an edit batch (prior to running verification checks), run:
  ```powershell
  graphify update . --no-cluster
  ```
  *(This refreshes the AST and edges locally without API cost or semantic reclustering. Do not run on every single file write).*
- **Harmless Zero-Node Warnings**: Non-code files (e.g. JSON configs, visual reports) may emit `warning: N source file(s) produced zero nodes`. This is expected AST behavior for non-extractable files and is not an error.
- **Never Run Routine Semantic Extraction**: `graphify extract` or `graphify update .` without `--no-cluster` requires provider credentials and costs tokens &mdash; do not run semantic extraction during routine editing sessions.
