# Ponytail vs. Aedile: Game Generation Benchmark, Deep Architecture Breakdown & Security Audit

- **Date**: 2026-11-20
- **Local Model**: `qwen3:4b` via Ollama (`temperature=0.0`, `num_predict=2200`, `think=False`)
- **Python**: `3.15.2` | **Node.js Syntax Verifier**: `node --check`

---

## 1. Game Generation & Verification Benchmark (Snake & Apple + Dino Runner)

Both **Ponytail** (`AGENTS.md`) and **Aedile** (`aedile map` + `aedile_consult`) were used as system contexts for `qwen3:4b` to generate two single-file HTML5 Canvas games (`snake.html` and `dino.html`). Each output was saved and verified with `html.parser`, `node --check`, and a 9-point mechanics/visual audit.

### Measured Results

| Game | Tool | Prompt Tokens | Output Tokens | Latency (s) | LOC | `<canvas>` | `node --check` (JS Valid) | Checks Passed | Playable |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Snake & Apple** | Ponytail | 697 | 2200 | 45.08s | 66 | No | **FAIL** | 5/9 | **No** |
| **Snake & Apple** | **Aedile** | **524** | 2200 | 45.14s | 28 | **Yes** | **PASS** | **7/9** | No *(missing `keydown`/visuals)* |
| **Dino Runner** | Ponytail | 696 | 2200 | 45.00s | 49 | No | **FAIL** | 4/9 | **No** |
| **Dino Runner** | **Aedile** | **523** | 2200 | 61.42s | 54 | No | **FAIL** | 2/9 | **No** |

### Honest Observations
- **Prompt Token Efficiency**: Aedile used **~25% fewer prompt tokens** (`523–524` vs. `696–697`) than Ponytail on both game tasks.
- **Code Validity**: On Snake & Apple, Aedile produced valid `<canvas>` + valid JS (`node --check` passed, `7/9` checks), whereas Ponytail failed JS syntax (`5/9`).
- **4B Model Limitation**: Under a single-shot 2,200-token budget, `qwen3:4b` frequently leaked planning prose containing `<!DOCTYPE html>` / `<script>` mentions before emitting the final code block, causing truncated or unplayable one-shot HTML outputs on Dino Runner for both tools. Larger coding models (or multi-turn MCP tool loops) are required for full playable single-shot Canvas games.

---

## 2. Deep Repository Breakdown: Core Features

### Ponytail (`dietrichgebert/ponytail`)
- **Prompt Ruleset (`skills/ponytail/SKILL.md`, `AGENTS.md`)**: 6-rung minimalism ladder (*Need to exist → Reuse → Stdlib/Native → Installed Dep → One-liner → Minimum working diff*) + `lite | full | ultra | off` intensity modes.
- **Regex Codebase Map (`hooks/ponytail-map.js`)**: Zero-dep Node script emitting a 2,000-char symbol summary at `SessionStart`, prioritizing `shared`/`util`/`lib`/`core` folders.
- **Multi-Host Lifecycle Hooks (`hooks/*.json`, `hooks/ponytail-subagent.js`)**: `SessionStart`, `SubagentStart`, and `UserPromptSubmit` across 20+ agent hosts.
- **Workflow Skills**: `/ponytail-review` (caller-aware diff review), `/ponytail-audit` (whole-repo ranked audit), `/ponytail-debt` (`shortcut:` ledger).
- **Observability (`hooks/band/`)**: Claude Code statusline band + local session board.

### Aedile (`aaryanrwt/aedile` v1.1.0)
- **Deterministic AST & Graph Core (`src/aedile/core/`)**: Python 3.11–3.15 `ast` parser (including PEP 810 `lazy import` awareness) + polyglot TS/JS, Go, and Rust structural parsers (`polyglot.py`), feeding Tarjan SCC `ArchitectureGraph`.
- **Pre-Edit In-Memory Simulator (`ArchitectureVerifier`)**: Simulates `add`, `modify`, and `delete` changes in-memory against cycle, layer, boundary, naming, and dangling-import rules before a single file is written.
- **AST Codebase Map (`mapper.py`) & Zero-Config Inference (`inference.py`)**: Token-budgeted AST symbol + layer map (`aedile map`) and automatic layer inference.
- **6-Tool Compact MCP Server (`mcp/server.py`)**: `aedile_consult`, `aedile_verify_architecture`, `aedile_map`, `aedile_graph`, `aedile_review`, `aedile_debt` with **Observed vs. Inferred** provenance tags.
- **CI/CD & Governance (`__main__.py`, `baseline.py`, `reporter.py`, `plugins.py`, `monorepo.py`)**: `aedile check` with `.aedile/baseline.json` regression gating, SARIF 2.1.0, self-contained HTML dashboards, custom `BaseRule` plugins, and monorepo boundary checks.

---

## 3. Security & Reliability Audit (Vulnerabilities Found & Fixed)

### Ponytail Vulnerabilities Observed
1. **No Import Graph / Pre-Edit Verification**: Cannot detect circular imports, layer violations, or dangling imports on file deletion (`0/3` architectural hazards caught in our 12-prompt `qwen3:4b` benchmark).
2. **Regex-Only Map Limitations (`hooks/ponytail-map.js:L25-L33`)**: Misses multi-line signatures, nested definitions, and dynamic exports.
3. **`git ls-files` Timeout Fallback (`hooks/ponytail-map.js:L39-L59`)**: Falls back to `fs.readdirSync` without `.gitignore` rules if `git ls-files` fails or exceeds 3s.
4. **Shared State Race (`hooks/ponytail-runtime.js:L49-L66`)**: Hosts without `CLAUDE_PROJECT_DIR` share one global `.ponytail-active` file across concurrent sessions.

### Aedile Vulnerabilities Found & Fixed in `v1.1.0`
1. **Untrusted Plugin Code Execution (`src/aedile/core/plugins.py`)** — *FIXED*:
   - *Issue*: `load_custom_rules()` executed `.aedile/rules/*.py` automatically on any scanned repo without opt-in or symlink containment.
   - *Fix*: Added `allow_plugins: bool = False` opt-in on `Config` and enforced `os.path.realpath()` containment inside `rules_dir`.
2. **Symlink Escape in `ArchitectureVerifier` (`src/aedile/core/verifier.py`)** — *FIXED*:
   - *Issue*: Path traversal check used `os.path.abspath()` instead of `os.path.realpath()`.
   - *Fix*: Switched to `os.path.realpath()` for both `filepath` and `safe_project_root`.
3. **Git Flag Injection in `reviewer.py` (`src/aedile/core/reviewer.py`)** — *FIXED*:
   - *Issue*: Unvalidated `base_ref` passed directly to `git diff --name-only <base_ref>`.
   - *Fix*: Rejected `base_ref` starting with `-` or containing whitespace/null bytes, and added `"--"` separator.
4. **Regex ReDoS Risk in `NamingPattern` (`src/aedile/shared/config.py`)** — *FIXED*:
   - *Issue*: Unbounded regex lengths from `aedile.toml`.
   - *Fix*: Enforced a 512-character maximum pattern length with `ConfigError`.
5. **Comment-Anchor & `DeadCodeRule` False Positives (`debt.py`, `dead_code.py`)** — *FIXED*:
   - *Issue*: `debt.py` matched `# shortcut:` inside string literals, and `dead_code.py` flagged `ast.NodeVisitor.visit_*` methods.
   - *Fix*: Anchored `_DEBT_RE` to comment-only lines (`^\s*(#|//|/\*)`) and exempted `method` / `visit_*` symbols from cross-file import checks.
