# REA-Methodology Reverse-Engineering Analysis: `EL4CTEO/fast-anything`

- **Target**: `https://github.com/EL4CTEO/fast-anything`
- **Methodology**: `morluto/rea` evidence-first static inspection (Observed facts, Derived architecture, Inferred trade-offs, Unknowns, and Aedile integration).
- **Aedile Polyglot Scan**: `21` Rust source files in `src/`, `21` nodes, `20` directed edges, `0` cycles.

---

## 1. Observed Facts (Source & Contract Evidence)

1. **Core Purpose (`README.md:L17-L20`, `src/mcp.rs:L11-L13`)**:
   - Profiles an existing app, ranks hot functions by runtime share × Rust portability, records up to 500 real calls, scaffolds a single-function Rust crate (`PyO3` / `napi-rs` / C ABI), verifies exact output parity on recorded + edge-case inputs, and swaps the port in via a reversible marked block.
2. **8-Tool MCP Surface (`src/mcp.rs:L22-L67`)**:
   - `fast_scan`, `fast_port`, `fast_verify`, `fast_enable`, `fast_disable`, `fast_bench`, `fast_report`, `fast_status`.
3. **Hotspot Ranking & Outermost-Caller Coverage (`src/hotspot.rs:L50-L90`)**:
   - Computes `share = cumtime / wall`, `score = share * portability`, and marks inner functions as `covered_by` an outermost portable caller in the same file when `caller.share >= 0.9 * inner.share` (so FFI boundary crossings happen once instead of per inner call).
4. **Shareable Visual Reporting (`src/report.rs:L30-L90`)**:
   - Emits `.fast/report.md` and a dark-theme `.fast/report.svg` card showing speedup, before/after bars, and verified call counts.
5. **Environment Diagnostics (`src/doctor.rs`)**:
   - Verifies Rust toolchain, language runtimes, and installed agent integrations before running workflows.

---

## 2. Derived Architecture

```text
CLI / MCP (src/main.rs, src/mcp.rs)
   │
   ▼
Pipeline Orchestrator (src/pipeline.rs)
   ├── Profiler & Ranker (src/hotspot.rs)
   ├── Language Drivers (python.rs, node.rs, golang.rs, ruby.rs, java.rs, php.rs, cfamily.rs)
   ├── Differential Verifier (src/verify / pipeline::verify)
   ├── State & Reversible Patcher (src/state.rs)
   └── Report Card Generator (src/report.rs -> report.md + report.svg)
```

---

## 3. Inferred Trade-Offs & Unknowns

- **Strengths**: Reversible marked-block edits (`FAST_ANYTHING_DISABLE=1`), outermost-loop ranking (`covered_by`), differential verification before enabling, and crisp PR-ready SVG report cards.
- **Limitations / Unknowns**: Assumes deterministic, pure-data functions; cross-language FFI overhead can outweigh gains on small inputs; requires `rustup`/native toolchains installed on the host.

---

## 4. Capabilities Implemented in Aedile

1. **`HotspotProfiler` (`src/aedile/core/hotspots.py` + `aedile hotspots` / `aedile_hotspots`)**: Zero-dependency `cProfile`/`pstats` profiler that ranks Python functions by `cumtime_share × portability` and computes `covered_by` outermost callers.
2. **PR Report Card (`to_card_svg()` in `src/aedile/core/reporter.py` + `aedile check --format card`)**: Dark-theme SVG summary card of architectural health, risk score, and prevented violations.
3. **`aedile doctor` (`src/aedile/cli/doctor.py`)**: Checks Python `3.13–3.15`, `git`, `ruff`, `mypy`, cache/baseline health, and agent MCP/hook registrations.
