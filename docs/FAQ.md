# Aedile FAQ

### How do I adopt Aedile on an existing repo without fixing old violations first?
Snapshot current findings into `.aedile/baseline.json`, then run CI with `--baseline`:

```bash
aedile check --update-baseline
aedile check --baseline
```

Only *new* architectural regressions will fail the build.

### How does Aedile handle Python 3.15 `lazy import` (PEP 810)?
`PythonParser` records `is_lazy` on every `Import`. If a dependency cycle consists *only* of PEP 810 lazy imports, `CycleRule` downgrades it from `error` to `warning` and includes a cycle-breaking hint.

### Can Aedile analyze languages other than Python?
Yes. Alongside Python `3.13–3.15` (`ast`), Aedile includes zero-dependency structural parsers in `src/aedile/core/polyglot.py` for TypeScript, JavaScript (`tsconfig.json` aliases, ES/CommonJS), Go, and Rust. Enable them in `aedile.toml` under `languages = ["python", "typescript", "go", "rust"]`.

### How do I inspect module hubs, paths, or performance hotspots?
- `aedile insights` — shows `god_nodes`, subsystem communities, cross-community bridges, and architectural questions.
- `aedile explain <module>` / `aedile path <src> <dst>` — inspects coupling, blast radius, and shortest dependency paths.
- `aedile hotspots <script.py>` — runs `cProfile` and ranks functions by `cumtime_share × portability` with `covered_by` outermost-caller detection.
- `aedile audit` — runs a ranked whole-repo audit (Must / Should / Nice to have).

### How do I export graphs for Gephi, Neo4j, or PRs?
```bash
aedile graph --format graphml --output graph.graphml
aedile graph --format cypher --output graph.cypher
aedile check --format card --output aedile-card.svg
```

### How do I track intentional shortcuts or deferred refactors?
Mark them in code comments with a ceiling and upgrade trigger:

```python
# shortcut: polling every 5s, switch to inotify if >10k files
```

Run `aedile debt` (or call `aedile_debt` via MCP) to list all markers and flag `[no-trigger]` comments.

### Does Aedile execute custom `.aedile/rules/*.py` plugins automatically?
No. Untrusted repository plugins are blocked by default. Enable them explicitly by setting `allow_plugins = true` under `[project]` in `aedile.toml`.
