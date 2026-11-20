<p align="center">
  <img src="images/logo.jpg" alt="Aedile Mascot Logo" width="200"/>
</p>

<h1 align="center">Aedile</h1>

<p align="center">
  <strong>Before an AI writes code, it should prove that the code deserves to exist.</strong>
</p>

<p align="center">
  <a href="https://github.com/aaryanrwt/aedile/actions/workflows/ci.yml">
    <img src="https://github.com/aaryanrwt/aedile/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI Status"/>
  </a>
  <a href="https://pypi.org/project/aedile/">
    <img src="https://img.shields.io/pypi/v/aedile.svg" alt="PyPI Version"/>
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.13%20--%203.15-blue.svg" alt="Python Versions"/>
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/>
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Code Style: Ruff"/>
  </a>
</p>

<p align="center">
Aedile is an engineering intelligence layer for AI coding assistants. It parses your repository into a live AST and dependency graph before code generation begins—surfacing existing helpers, enforcing layer boundaries, catching circular imports, and preferring standard libraries—all locally with zero external dependencies.
</p>

---

```text
          Coding Agent
               │
               ▼
        "Build auth helper"
               │
               ▼
           Aedile MCP
      ┌──────────────────────────┐
      │ Existing symbol? (BM25)  │
      │ Stdlib / declared dep?   │
      │ Tarjan import cycle?     │
      │ Layer / delete hazard?   │
      └──────────────────────────┘
               │
               ▼
   Verified, minimal implementation
```

---

## Why Aedile?

Modern coding assistants know how to write code. They usually don't know your architecture.

Static prompt rules drift as the context window fills, and regex-only maps miss nested definitions, import graphs, and layer boundaries. That leads to:

- duplicate utilities
- unnecessary third-party dependencies
- circular imports
- broken layer boundaries and dangling deletions

Aedile verifies the repository deterministically before code is written, giving coding assistants real AST and graph facts instead of relying on prompts alone.

---

## Quick Example

**Without Aedile**

```text
AI: "I'll add a new cycle detector and install a helper."
↓
Repository already has ArchitectureGraph.find_all_cycles() and tomllib.
↓
Duplicate logic + extra dependency.
```

**With Aedile**

```text
Aedile [Observed: AST/Graph]:
  "Reuse ArchitectureGraph.find_all_cycles() in src/aedile/core/graph.py:L49."
  "ARCHITECTURAL VIOLATION: importing cli from shared violates layer order."
↓
AI reuses the existing method and respects layer boundaries.
```

---

## How It Works

Aedile runs locally as a 6-tool Model Context Protocol (MCP) server and standalone CLI:

1. **Session Map (`aedile map`)**: Emits a token-budgeted, AST-verified symbol & layer map at session start (`shared`/`core`/`util` first).
2. **Pre-Edit Consultation (`aedile_consult` / `aedile_verify_architecture`)**: Runs BM25/IDF symbol reuse search, `tomllib` dependency checks, and in-memory `add`/`modify`/`delete` graph simulation.
3. **Blast-Radius Review & Debt (`aedile review` / `aedile debt`)**: Traces transitive dependents outside the diff and tracks `# shortcut:` / `# aedile-waive:` debt markers.
4. **CI Gate (`aedile check`)**: Zero-config layer inference, `.aedile/baseline.json` regression tracking, SARIF 2.1.0, and self-contained HTML dashboards.

---

## Install & Setup

```bash
pip install aedile
```

Configure MCP servers and `SessionStart` / `SubagentStart` hooks automatically for your local agents (creates `.aedile.bak` backups):

```bash
aedile setup
```

Or run `aedile setup --dry-run` to preview changes first. See [SUPPORTED_AGENTS.md](SUPPORTED_AGENTS.md) for manual configs.

---

## Commands & MCP Tools

| CLI Command | MCP Tool | What it does |
|---|---|---|
| `aedile` | `aedile_consult` | Start MCP server / consult reuse, stdlib, deps & pre-edit checks |
| — | `aedile_verify_architecture` | Simulate `add` / `modify` / `delete` changes before writing files |
| `aedile map` | `aedile_map` | Emit token-budgeted AST symbol & layer map |
| `aedile graph` | `aedile_graph` | Export Mermaid/SVG dependency graph or query module blast radius |
| `aedile review` | `aedile_review` | Caller-aware blast-radius review ranked Must / Should / Nice to have |
| `aedile debt` | `aedile_debt` | Harvest `# shortcut:` / `# aedile-waive:` debt ledger |
| `aedile check` | — | Full-repo CI gate (`text`, `json`, `sarif`, `html`) with `--baseline` |
| `aedile mode` | — | Set intensity mode (`lite`, `full`, `ultra`, `off`) |
| `aedile board` | — | Show local reuse & token-savings telemetry or export HTML board |

---

## Benchmarks (Real Local Run)

Measured side-by-side on local **`qwen3:4b`** via Ollama (`Python 3.15.2`, `temperature=0.0`, `num_predict=160`) across **12 engineering prompts** (reuse, stdlib, layer violations, import cycles, file deletion, blast radius, debt ledger):

| Metric | Ponytail (`AGENTS.md` + `ponytail-map.js`) | Aedile (`aedile map` + `aedile_consult`) |
| :--- | :---: | :---: |
| **LLM Response Hit Rate** | 2/12 (16.7%) | **10/12 (83.3%)** |
| **Deterministic Tool Guarantee** | 0/12 (no AST/graph tool) | **11/12 (91.7%)** |
| **Avg Prompt Tokens** | 794.6 | **752.8** |

Full methodology, per-prompt tables, and game-generation benchmarks: [benchmarks/BENCHMARKS.md](benchmarks/BENCHMARKS.md) and [benchmarks/GAME_BENCHMARK_AND_AUDIT.md](benchmarks/GAME_BENCHMARK_AND_AUDIT.md).

---

## FAQ

**Does Aedile require internet access or API keys?**
No. All AST parsing, graph simulation, caching, and telemetry stay 100% local on your machine.

**Which languages and Python versions are supported?**
Python `3.11–3.15` (including PEP 810 `lazy import` cycle awareness) is built-in via stdlib `ast`, alongside zero-dependency structural parsers for TypeScript/JavaScript, Go, and Rust.

**How do I adopt Aedile on a legacy repo without fixing everything at once?**
Run `aedile check --update-baseline`, then gate CI with `aedile check --baseline` so only *new* architectural regressions fail the build.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Decision Ladder](docs/DECISION_LADDER.md)
- [Competitor Comparison](docs/COMPETITORS.md)
- [FAQ](docs/FAQ.md)
- [Supported Agents](SUPPORTED_AGENTS.md)
- [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md)
- [Security Policy](SECURITY.md)

---

## Contributing & License

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Aedile is released under the [MIT License](LICENSE).
