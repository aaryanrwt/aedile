# Aedile Roadmap & Upcoming Version Buffs (v1.1 – v1.5)

This document outlines the planned engineering upgrades ("version buffs") for Aedile following the `v1.0.0` release and Python 3.15 migration. Each milestone combines:

1. **Core Aedile Architectural Hardening** (addressing gaps in `src/aedile/` and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
2. **Competitive Differentiation** informed by analyzing `dietrichgebert/ponytail` (UX, lifecycle hooks, codebase maps, review/debt workflows, observability) and `morluto/rea` (evidence provenance, compact MCP schemas, idempotent multi-agent setup).

---

## Competitive Analysis: Why Aedile Can Win

| Capability | Ponytail | REA | Aedile (`v1.0.0` → `v1.5`) |
|---|---|---|---|
| **Enforcement Mechanism** | Prompt rules + regex map | Evidence-backed MCP + CLI | **AST + Tarjan SCC graph + in-memory `ArchitectureVerifier` + MCP** |
| **Codebase Map** | Regex-only (`ponytail-map.js`, 2k char budget) | Deep binary/JS/runtime inspection | **AST-verified symbol + layer map (`v1.1`)** — no missed nested/typed definitions |
| **Pre-Edit Verification** | Prompt guidance only | Read-only investigation | **In-memory `add`/`modify`/`delete` graph simulation before code is written** |
| **Subagent & Multi-Host Hooks** | `SessionStart` + `SubagentStart` + 20+ agents | `rea setup` with idempotent backups | **Unified `aedile setup` + `SubagentStart` + `PreToolUse` hooks (`v1.2`)** |
| **Diff & Repo Audits** | `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt` | Structured evidence & unknowns | **Caller-aware blast-radius review + `shortcut:`/`waive:` debt ledger (`v1.3`)** |
| **CI/CD & Governance** | None (local prompt skill) | CLI JSON + exit codes | **CLI `aedile check`, baselines, SARIF 2.1.0, HTML dashboard (`v1.2`)** |

**Aedile's Core Advantage:** Ponytail relies on regexes and prompt compliance—it cannot construct an import graph, detect Tarjan SCC cycles, enforce layer boundaries, or gate CI. By pairing Aedile's deterministic AST/graph engine with Ponytail's zero-friction session UX and REA's evidence-first MCP discipline, Aedile delivers both **prompt-free prevention** and **hard architectural guarantees**.

---

## Current Baseline (`v1.0.0`)

- **Runtime**: Python `>=3.11` through `3.15` (PEP 810 `lazy import` AST support included).
- **MCP Server**: Single stdio JSON-RPC tool (`aedile_consult`) in `src/aedile/mcp/server.py`.
- **Core Analysis**: Python `ast`-based `PythonParser`, Tarjan SCC `ArchitectureGraph`, `Scanner`, `ArchitectureVerifier` (`add`/`modify` simulation), `SimilarityEngine` (token Jaccard + static `STDLIB_MAP`/`DEP_MAP`), and 6 rules (`CycleRule`, `LayerRule`, `BoundaryRule`, `NamingRule`, `DeadCodeRule`, `DuplicateRule`).
- **CLI**: `python -m aedile` (MCP stdio server) and `python -m aedile compile-rules`.

---

## v1.1 — Core Hardening, AST Codebase Map & Compact MCP

Focus: Fix `v1.0.0` runtime rough edges, add zero-search session maps, and adopt REA-style MCP efficiency.

- **ScanCache Path & Incremental Speed Buff**
  - Fix `AedileMcpServer` passing `project_root` instead of `.aedile/cache.json` to `ScanCache`, and pair `os.stat` `(mtime_ns, size)` pre-filtering with SHA-256 hashing so unchanged files skip disk reads.
- **AST-Backed Codebase Map (`aedile map`)**
  - Emit a token-budgeted (default 2,000-char), one-line-per-directory symbol map for `SessionStart` injection—prioritizing `shared`, `core`, `util`, and `service` directories first (matching Ponytail's `ponytail-map.js` UX, but backed by `PythonParser` AST + layer metadata instead of brittle regex).
- **Richer `PythonParser` & PEP 810 `lazy import` Semantics**
  - Index class methods (`MethodDef`), type aliases (`TypeAlias`), and module-level constants alongside top-level functions and classes.
  - Distinguish PEP 810 `lazy import` edges from eager imports in `ArchitectureGraph` and `CycleRule` (flagging eager cycles as `error` while annotating lazy-only cycles).
- **REA-Style Compact MCP Schemas & Evidence Provenance**
  - Keep `tools/list` schemas compact to minimize agent context tax, tag every `aedile_consult` finding as **observed** (AST/graph) vs. **inferred** (heuristic), and expose `aedile_verify_architecture` and `aedile_graph` tools.
- **Structural Dependency & Expanded Stdlib Awareness**
  - Upgrade `SimilarityEngine.check_dependencies()` to parse `pyproject.toml` via `tomllib` instead of raw text regex, and expand `STDLIB_MAP` / `DEP_MAP` (`tomllib`, `functools`, `itertools`, `asyncio`, `httpx`, `pydantic`, `fastapi`, `pytest`).
- **`delete` Simulation in `ArchitectureVerifier`**
  - Support `action: "delete"` in `verify_changes()` so agents catch dangling imports before removing modules.

---

## v1.2 — Standalone CLI, Multi-Agent Setup (`aedile setup`) & CI/CD

Focus: Deliver one-command multi-agent onboarding (inspired by `rea setup` & Ponytail's 20-agent reach) alongside CI/CD enforcement.

- **One-Command Multi-Agent Setup (`aedile setup`)**
  - Auto-detect installed agents (Claude Code, Cursor, Codex, Windsurf, Cline, Gemini CLI, Copilot), preview planned changes, create backups, and idempotently register Aedile's MCP server, rule files, and lifecycle hooks.
- **Subagent Injection & Intensity Modes (`lite | full | ultra | off`)**
  - Ship `SessionStart`, `SubagentStart` (ensuring spawned subagents inherit Aedile's codebase map and architectural rules), and `PreToolUse` hook templates.
  - Support configurable strictness levels (`lite`: warn only; `full`: standard ladder + boundary checks; `ultra`: block speculative abstractions & enforce strict test-on-risky-logic).
- **Full CLI (`src/aedile/cli/`)**
  - `aedile check`: Full-repo CI architectural gate with configurable fail thresholds and exit codes.
  - `aedile graph`: Export Mermaid (`.mmd`) and radial SVG dependency diagrams.
  - `aedile init`: Auto-detected `aedile.toml` generator.
- **Zero-Config Layer Inference (`src/aedile/core/inference.py`)**
  - Automatically infer `layer_order` and `layer_mappings` from project structure (`cli`/`api`, `core`/`domain`, `infrastructure`, `shared`) when `aedile.toml` is absent.
- **Baseline & Regression Tracking (`src/aedile/core/baseline.py`)**
  - Snapshot existing violations into `.aedile/baseline.json` so legacy repos fail CI only on *new* regressions.
- **SARIF 2.1.0 & HTML Dashboards (`src/aedile/core/reporter.py`)**
  - Emit GitHub Code Scanning SARIF reports and self-contained interactive HTML architecture dashboards with zero external dependencies.

---

## v1.3 — Semantic Intelligence, Blast-Radius Review & Debt Ledger

Focus: Beat static diff reviews and keyword search with graph-powered impact analysis and tracked technical debt.

- **AST-Structural & BM25 Similarity (`SimilarityEngine`)**
  - Combine BM25 ranking over signatures/docstrings with normalized AST subtree fingerprinting so `DuplicateRule` and `aedile_consult` detect structurally identical logic even when symbols are renamed.
- **Blast-Radius & Caller-Aware Review (`aedile review`)**
  - Compute fan-in, fan-out, instability ($I = \frac{C_e}{C_a + C_e}$), and transitive dependents in `ArchitectureGraph`.
  - When reviewing a diff or proposed change, inspect connected callers/callees *outside* the diff and output ranked, plain-English findings (*What it is → Problem → Fix → Impact if skipped*, grouped as **Must fix / Should fix / Nice to have**).
- **Architectural Debt Ledger (`aedile debt`)**
  - Collect `# shortcut: <ceiling>, <upgrade trigger>` and `# aedile-waive: <reason>` comments across the repo into a structured debt ledger, flagging `no-trigger` shortcuts that risk silently rotting.
- **Incremental File Watcher (`src/aedile/infrastructure/watcher.py`)**
  - Keep `AedileMcpServer`'s symbol index and `ArchitectureGraph` warm in memory on file edits instead of re-walking the tree on every `aedile_consult` call.

---

## v1.4 — Polyglot AST & Dependency Graph

Focus: Activate the multi-language stubs in `LanguageDetector` (`src/aedile/core/parser.py`) with real structural parsing—surpassing Ponytail's regex-only multi-language map.

- **TypeScript & JavaScript Parser**
  - Parse ES module (`import`/`export`) and CommonJS (`require`) dependencies, resolve `tsconfig.json` path aliases, and enforce barrel-file (`index.ts`) boundaries.
- **Go & Rust Parsers**
  - Parse Go `import` blocks (enforcing `internal/` package visibility) and Rust `use`/`mod` trees (enforcing `pub(crate)` boundaries).
- **Unified Polyglot IR**
  - Normalize all languages into `SourceFile`, `Import`, and `Symbol` so `CycleRule`, `LayerRule`, `BoundaryRule`, `ArchitectureGraph`, and `aedile map` operate identically across mixed-language repositories.

---

## v1.5 — Policy-as-Code, Monorepos & Live Observability

Focus: Scale to multi-package organizations and give developers live proof of Aedile's impact.

- **Custom Rule Plugin SDK**
  - Load project-specific Python rules (`BaseRule` subclasses) from `.aedile/rules/` or entry points declared in `aedile.toml`.
- **Monorepo & Workspace Federation**
  - Support `uv` workspaces, multi-package `pyproject.toml` monorepos, and `pnpm` workspaces with cross-package dependency matrices and forbidden-edge policies.
- **Aedile Telemetry Band & Local Board**
  - Local-only statusline & HTML board tracking **codebase reuse rate** (existing symbols reused vs. new symbols created), **prevented cycles & layer violations**, and **estimated token savings** across sessions.
- **Automated Cycle-Breaking & Refactoring Hints**
  - Suggest concrete cycle-breaking refactors (interface/protocol extraction, dependency inversion, or PEP 810 `lazy import` placement) whenever `CycleRule` or `LayerRule` triggers.
