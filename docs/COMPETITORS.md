# Competitor Architecture Comparison

Technical comparison between Aedile and other AI coding guardrails and static architecture linters.

---

| Tool | Ecosystem | Enforcement | Key Strengths | Limitations | License |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Aedile (`v1.1.0`)** | Python `3.11–3.15` + TS/JS, Go, Rust | AST + Tarjan SCC graph + MCP + CLI | Zero deps, offline-first, pre-edit `add`/`modify`/`delete` simulation, AST codebase map, SARIF 2.1.0, HTML dashboard, baselines, blast-radius review | Polyglot parsers are structural (no full type-checker) | MIT |
| **Ponytail** | Prompt skill + Node hooks | Static prompt rules + regex map | Multi-host hooks (20+ agents), `lite`/`full`/`ultra` modes, `/ponytail-review`, `/ponytail-debt`, Claude band | Regex-only map, no import graph, no cycle/layer detection, no pre-edit verification, no CI gate | MIT |
| **Import Linter** | Python | Static import contracts | Mature Python import contract syntax | No incremental cache, no dead code/duplication/MCP, no SARIF or HTML dashboard | BSD-3-Clause |
| **Dependency Cruiser** | JS / TS | Dependency graph rules | Fast JS/TS validation, SVG/Dot graphs | JS/TS only, no AI/MCP pre-edit consultation or debt ledger | MIT |
| **Ruff** | Python | AST linting & formatting | Extremely fast Rust implementation | File-level linter; does not build cross-module Tarjan SCC graphs or enforce layer boundaries | MIT |
| **ArchUnit** | Java | Unit-test architecture assertions | Expressive Java API, deep test integration | JVM only, high boilerplate, no AI/MCP integration | Apache-2.0 |
