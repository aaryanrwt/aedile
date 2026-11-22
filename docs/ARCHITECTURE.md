# Aedile Architecture

Aedile enforces a strict inward dependency flow with **zero external runtime dependencies** (Python `3.13–3.15` standard library only).

```text
Presentation (src/aedile/cli/, src/aedile/mcp/, src/aedile/__main__.py)
       │
       ▼
Application  (scanner.py, mapper.py, inference.py, baseline.py,
              reporter.py, reviewer.py, verifier.py, optimizer.py,
              similarity.py, debt.py, plugins.py, monorepo.py,
              graph_insights.py, hotspots.py)
       │
       ▼
Domain       (models.py, graph.py, parser.py, polyglot.py, rules/*)
       │
       ▼
Infrastructure (cache.py, watcher.py, telemetry.py)
       │
       ▼
Shared       (config.py, errors.py, logging.py)
```

---

## Layers

### 1. Presentation (`src/aedile/cli/`, `src/aedile/mcp/`, `src/aedile/__main__.py`)
- **MCP Server (`mcp/server.py`)**: Stdio JSON-RPC 2.0 server exposing **11 compact-schema tools** (`aedile_consult`, `aedile_verify_architecture`, `aedile_map`, `aedile_graph`, `aedile_review`, `aedile_debt`, `aedile_explain`, `aedile_path`, `aedile_insights`, `aedile_audit`, `aedile_hotspots`) with **Observed vs. Inferred** provenance tags.
- **CLI (`__main__.py`, `cli/setup.py`, `cli/doctor.py`)**: Commands `check`, `graph`, `map`, `explain`, `path`, `insights`, `review`, `audit`, `debt`, `hotspots`, `doctor`, `setup`, `init`, `mode`, `board`, and `compile-rules`.

### 2. Application (`src/aedile/core/`)
- **Orchestration (`scanner.py`)**: Crawls enabled languages, checks `(mtime_ns, size)` + SHA-256 cache, builds `ArchitectureGraph`, runs built-in + opt-in plugin rules (`plugins.py`) and monorepo boundary checks (`monorepo.py`).
- **Pre-Edit Verification (`verifier.py`)**: Simulates `add`, `modify`, and `delete` changes in memory (with `realpath` symlink-escape protection) to catch cycles, layer violations, and dangling imports before files are written.
- **Intelligence (`similarity.py`, `optimizer.py`, `mapper.py`, `graph_insights.py`, `hotspots.py`, `reviewer.py`, `debt.py`)**: BM25/IDF symbol search, `tomllib` dependency parsing, token-budgeted AST maps, `god_nodes` / community clustering / `graph_diff`, `cProfile` hotspot ranking with `covered_by`, caller-aware reviews, whole-repo ranked audits, and `# shortcut:` / `# aedile-waive:` debt scanning.
- **Governance (`inference.py`, `baseline.py`, `reporter.py`)**: Zero-config layer inference, `.aedile/baseline.json` regression filtering, JSON, SARIF 2.1.0, HTML dashboard, and shareable dark-theme SVG report cards (`to_card_svg`).

### 3. Domain (`models.py`, `graph.py`, `parser.py`, `polyglot.py`, `rules/*`)
- **IR (`models.py`)**: `SourceFile`, `Import` (including PEP 810 `is_lazy`), `Symbol`, `Violation`, `ProjectMetrics`, `Report`.
- **Graph (`graph.py`)**: Tarjan's SCC cycle finder, lazy-only cycle detection, cycle-break hints, transitive blast radius, Martin instability ($I = \frac{C_e}{C_a + C_e}$), Mermaid, radial SVG, GraphML, and Cypher exporters.
- **Parsers (`parser.py`, `polyglot.py`)**: Python `ast` parser plus structural parsers for TypeScript/JavaScript (`tsconfig.json` aliases), Go, and Rust.
- **Rules (`rules/*`)**: `CycleRule`, `LayerRule`, `BoundaryRule`, `NamingRule`, `DeadCodeRule`, `DuplicateRule`.

### 4. Infrastructure (`src/aedile/infrastructure/`)
- **`cache.py`**: Incremental JSON cache (`.aedile/cache.json`) with `(mtime_ns, size)` fast-path and `AEDILE_MAX_CACHE_BYTES` (64 MiB default) memory-bomb cap.
- **`watcher.py`**: Zero-dependency `(mtime_ns, size)` diffing so the MCP server skips re-scanning unchanged workspaces.
- **`telemetry.py`**: Local-only `.aedile/telemetry.jsonl` counters, statusline, and HTML board.
