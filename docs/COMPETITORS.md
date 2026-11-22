# Competitor Architecture Comparison

Technical comparison between Aedile and other AI coding guardrails, knowledge-graph tools, and static architecture linters.

---

| Tool | Ecosystem | Enforcement | Key Strengths | Limitations | License |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Aedile (`v1.1.0`)** | Python `3.13–3.15` + TS/JS, Go, Rust | AST + Tarjan SCC graph + 12-tool MCP + CLI | Zero deps, offline-first, pre-edit `add`/`modify`/`delete` simulation, AST codebase map, `god_nodes`/communities, `cProfile` hotspots, CLI output compression (`compress`/`recall`/`gain`), SARIF 2.1.0, GraphML/Cypher/SVG cards, baselines | Polyglot parsers are structural (no full type-checker) | MIT |
| **RTK (`rtk-ai/rtk`)** | Rust CLI proxy | Post-execution CLI output filter | 100+ command filters (`pytest`, `git`, `cargo`), `<25ms` overhead, `rtk recall` failure recovery, SQLite `rtk gain` tracking | Post-hoc only (does not prevent duplicate code, circular imports, or layer violations before AI writes code) | MIT |
| **Ponytail** | Prompt skill + Node hooks | Static prompt rules + regex map | Multi-host hooks (20+ agents), `lite`/`full`/`ultra` modes, `/ponytail-review`, `/ponytail-debt`, Claude band | Regex-only map, no import graph, no cycle/layer detection, no pre-edit verification, no CI gate | MIT |
| **Graphify** | Python + Tree-sitter | Knowledge graph + Leiden clustering | ~40-language tree-sitter extraction, `god_nodes`, `surprising_connections`, GraphML/Cypher/Obsidian exports, doc/media semantic pass | Heavy external deps (`networkx`, grammars), read-only exploration (no pre-edit layer/cycle/delete gate) | Apache-2.0 / MIT |
| **fast-anything** | Rust CLI + 8-tool MCP | Profiler + Rust FFI verifier | Profiles hotspots (`covered_by`), ports pure functions to Rust, replays 500 real calls, PR `.svg` report card | Focused on runtime Rust porting rather than architectural boundaries or reuse | MIT |
| **Import Linter** | Python | Static import contracts | Mature Python import contract syntax | No incremental cache, no dead code/duplication/MCP, no SARIF or HTML dashboard | BSD-3-Clause |
| **Dependency Cruiser** | JS / TS | Dependency graph rules | Fast JS/TS validation, SVG/Dot graphs | JS/TS only, no AI/MCP pre-edit consultation or debt ledger | MIT |
| **Ruff** | Python | AST linting & formatting | Extremely fast Rust implementation | File-level linter; does not build cross-module Tarjan SCC graphs or enforce layer boundaries | MIT |
| **ArchUnit** | Java | Unit-test architecture assertions | Expressive Java API, deep test integration | JVM only, high boilerplate, no AI/MCP integration | Apache-2.0 |
