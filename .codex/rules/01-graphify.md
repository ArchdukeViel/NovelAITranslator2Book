# Graphify

Knowledge graph at `graphify-out/graph.json`. Use CLI commands:

- Query: `graphify query "<question>"`
- Path: `graphify path "<A>" "<B>"`
- Explain: `graphify explain "<concept>"`
- Update: `graphify update .`

Pre-commit hook rebuilds graph automatically after commits.
Do not commit graphify-out/ files — they are gitignored.
