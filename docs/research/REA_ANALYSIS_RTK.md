# Reverse Engineering Analysis: `rtk-ai/rtk`

- **Repository**: `https://github.com/rtk-ai/rtk` (85k+ GitHub stars, Rust CLI proxy)
- **Methodology**: Evidence-first Reverse Engineering Analysis (REA) — separating directly observed source facts from derived architecture, inferred trade-offs, and integration plan for Aedile.

---

## 1. Observed Facts (From Source Inspection)

1. **Token Estimation Formula (`README.md`, `src/core/tracking.rs`)**
   - RTK estimates token counts deterministically without external tokenizer dependencies using `bytes / 4` (standard ~4 chars/token heuristic).
   - `tracking.rs` persists every command execution (`input_tokens`, `output_tokens`, `savings %`, execution time, project path) in an SQLite database (`tracking.db`) with a 90-day default retention window (`DEFAULT_HISTORY_DAYS`) and exposes `rtk gain` for historical aggregation.

2. **Global Output Truncation Caps (`src/core/truncate.rs`)**
   - Defines uniform global caps rather than ad-hoc per-command magic numbers:
     - `CAP_ERRORS = 20`
     - `CAP_WARNINGS = 10`
     - `CAP_LIST = 20`
     - `CAP_INVENTORY = 50`
   - Provides underflow-safe `reduced(cap, by)` helpers so nested summaries never panic or overflow.

3. **Failure Recovery & Recall (`src/core/tee.rs`)**
   - When a command fails and raw output exceeds `MIN_FAILURE_BYTES`, RTK stores the raw output on disk and appends a compact recovery hint: `[full output: rtk recall <hash>]` or `[+N hidden: rtk recall <hash>]`.
   - This guarantees the LLM never loses critical debugging context even under aggressive compression.

4. **Pytest State-Machine Filter (`src/cmds/python/pytest_cmd.rs`)**
   - Uses a 4-state parser (`Header`, `TestProgress`, `Failures`, `Summary`) with `MAX_TRACEBACK_LINES = 3`, `MAX_ERROR_LINES = 4`, and `MAX_XFAIL = CAP_WARNINGS`.
   - Includes a safety fallback: if `exit_code != 0` and the filter produces an empty/no-tests result (meaning pytest crashed during collection or setup before reporting), it falls back to truncated ANSI-stripped raw output (`passthrough_max_chars`) rather than hiding the crash.

---

## 2. How `rtk-ai/rtk` Tests Itself (`.github/workflows/ci.yml`, `tests/`)

- **Multi-Gate CI**: Runs `check-test-presence` (verifying new filter modules include tests), `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets`, `cargo doc --no-deps`, `proxy` daemon checks, and an `oss` edition purity check.
- **Invariant & Property Tests**:
  - `tests/ls_never_worse_test.rs` + `src/core/guard.rs` (`never_worse(raw, filtered)`): asserts compressed output never exceeds raw token count.
  - `tests/fallback_integrity_test.rs`: verifies `.rtk-hook.sha256` integrity before dispatching fallback hooks.
  - `tests/stderr_only_failure_test.rs`, `tests/help_passthrough_fuzz_test.rs`, `tests/diff_byte_accuracy_test.rs`, `tests/windows_child_quoting_test.rs`.

## 3. Bugs, Edge Cases & Architectural Gaps Found in `rtk-ai/rtk`

1. **Windows Test Coverage Gap (`tests/ls_never_worse_test.rs`, `tests/fallback_integrity_test.rs`)**: Several core invariant tests are gated with `#![cfg(unix)]`, skipping those invariant checks on Windows hosts.
2. **Naive `never_worse` Exception Friction (`src/core/guard.rs`)**: Because `never_worse` compares raw vs. filtered token counts strictly, short 1-line diagnostics (such as `rtk diff` CRLF/LF notices or `ruff`'s empty `[]` output) exceed 1-line raw inputs and require manual per-caller bypasses.
3. **Post-Hoc Compression Only (No Pre-Write Gate)**: `rtk` has zero AST parsing, zero Tarjan cycle detection, zero layer-boundary enforcement, and zero symbol-reuse consultation. It compresses test logs *after* bloated or duplicated code has already been written.
4. **Brittle Text State Machine (`src/cmds/python/pytest_cmd.rs`)**: Relies on line-by-line regex/state parsing (`Header`, `TestProgress`, `Failures`, `Summary`), requiring `passthrough_max_chars` fallback if collection/conftest crashes before summary output.

---

## 4. Derived Architecture

```
LLM / Coding Agent
       │
       ▼  (runs command via proxy / tool)
[ Command Runner ] ──► executes subprocess, captures raw stdout/stderr
       │
       ├──► [ Failure Tee ] ──► on non-zero exit & large output, saves raw log by hash
       │                        emits `[full output: recall <id>]`
       │
       ├──► [ Domain Filter ] ──► state-machine / diff / lint compressor
       │                          enforces CAP_ERRORS=20, CAP_WARNINGS=10
       │
       └──► [ Telemetry Tracker ] ──► records raw_bytes, compressed_bytes, tokens_saved
```

---

## 3. Inferred Trade-offs & Gaps vs. Aedile

| Dimension | `rtk-ai/rtk` | Gap / Complementary Opportunity in Aedile |
|---|---|---|
| **When it acts** | **Post-execution**: compresses noisy CLI output *after* the agent already wrote code and ran tests. | **Pre-write + Post-execution**: Aedile blocks duplicate symbols, dead code, missing stdlib reuse, and circular imports *before* the AI writes code, AND compresses CLI/tool outputs afterward. |
| **Dependency & Runtime** | Compiled Rust binary (`rusqlite`, `regex`, `serde`, `chrono`). | Pure Python `>=3.13` stdlib (`sqlite3`, `hashlib`, `re`, `subprocess`), zero external dependencies. |
| **Token Waste Type** | Eliminates **tool-output bloat** (60–90% of `pytest`, `git diff`, `mypy`, `ruff` logs). | Eliminates **both** generation waste (unnecessary files/functions) **and** tool-output bloat. |

---

## 4. Aedile Integration Plan

1. **`src/aedile/core/compressor.py`** (Zero-dependency stdlib module):
   - Implement `CAP_ERRORS = 20`, `CAP_WARNINGS = 10`, `CAP_LIST = 20`, `MIN_FAILURE_BYTES = 512`.
   - Implement domain-aware compressors: `compress_pytest`, `compress_git_diff`, `compress_ruff_mypy`, and `compress_generic` with crash-safe passthrough fallback.
   - Implement `.aedile/recall/<sha256[:12]>.log` storage and `recall_output(hash_prefix)` so compressed failures remain 100% recoverable.
   - Compute exact token savings (`raw_bytes // 4 - compressed_bytes // 4`) and record them in `TelemetryStore`.
2. **CLI & MCP Exposure**:
   - Add `aedile compress <cmd...>`, `aedile recall <id>`, and `aedile gain` in `src/aedile/__main__.py`.
   - Add `aedile_compress` as the 12th MCP tool in `src/aedile/mcp/server.py`.
