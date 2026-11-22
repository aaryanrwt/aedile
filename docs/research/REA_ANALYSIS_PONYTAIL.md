# REA-Methodology Reverse-Engineering Analysis: `dietrichgebert/ponytail`

- **Target**: `https://github.com/dietrichgebert/ponytail` (`v5.3.3`)
- **Methodology**: `morluto/rea` evidence-first static inspection + Aedile polyglot/debt scan (`22` JS/TS files across `hooks/`, `scripts/`, `pi-extension/`, `22` nodes, `22` directed edges, `0` cycles, `37` debt markers).

---

## 1. Observed Facts (Source & Contract Evidence)

1. **Prompt-Driven Minimalism (`skills/ponytail/SKILL.md:L19-L45`, `AGENTS.md`)**:
   - Enforces a 6-rung minimalism ladder (*Need to exist -> Reuse -> Stdlib/Native -> Installed Dep -> One-liner -> Minimum diff*) with `off | lite | full | ultra` intensity modes (`hooks/ponytail-config.js:L17-L34`).
2. **Regex Codebase Map (`hooks/ponytail-map.js:L1-L111`)**:
   - Injects a 2,000-char directory symbol map at `SessionStart`, prioritizing `shared`/`util`/`lib`/`core` directories. Self-documents at `L9`: *"regex, not a parser. Misses nested or dynamic definitions"*.
3. **Multi-Host Lifecycle Hooks (`hooks/claude-codex-hooks.json`, `hooks/ponytail-subagent.js`)**:
   - `SessionStart`, `SubagentStart` (ensures spawned subagents inherit rules), and `UserPromptSubmit` across 20+ coding agents.
4. **Structured Review, Audit & Debt Workflows (`skills/ponytail-review/SKILL.md`, `ponytail-audit/SKILL.md`, `ponytail-debt/SKILL.md`)**:
   - Caller-aware diff reviews (*What this is -> Problem -> Fix -> If we skip it*, ranked *Must fix / Should fix / Nice to have*), whole-repo ranked audits, and `shortcut: <ceiling>, <upgrade>` debt harvesting.
5. **Live Telemetry Band (`hooks/band/metrics.ts`, `board.ts`, `register.tsx`)**:
   - Local statusline & HTML board tracking cost, tokens, reuse %, and test pass state.

---

## 2. Derived Architecture

```text
Host Hooks (SessionStart / SubagentStart / UserPromptSubmit)
   │
   ├── ponytail-config.js / ponytail-runtime.js (mode + host detection)
   ├── ponytail-map.js (2k-char regex symbol map)
   ├── ponytail-instructions.js (mode-filtered SKILL.md rules)
   └── band/ (metrics.ts + register.tsx + board.ts -> local dashboard)
```

---

## 3. Inferred Trade-Offs & Unknowns

- **Strengths**: Zero-friction session UX, subagent rule propagation, structured plain-English review/audit formats, and local telemetry band.
- **Observed Weaknesses (`37` debt markers, `19` `[no-trigger]`)**:
  - Regex-only symbol & reuse detection (`hooks/ponytail-map.js:L9`, `hooks/band/metrics.ts:L13`, `register.tsx:L312`).
  - No import graph, no Tarjan SCC cycle detection, no layer boundary checks, no pre-edit verification (`0/3` architectural hazards caught in our `qwen3:4b` benchmark).
  - Uncached 3s-timeout map (`hooks/ponytail-activate.js:L65`) and shared-mode race when `CLAUDE_PROJECT_DIR` is absent (`hooks/ponytail-runtime.js:L49`).

---

## 4. Capabilities Implemented in Aedile

1. **Already Implemented (`v1.1.0`)**: AST-backed `aedile map`, `aedile setup` (`SessionStart` + `SubagentStart`), `aedile mode` (`lite|full|ultra|off`), `aedile review`, `aedile debt`, and `aedile board`.
2. **Added Now (`aedile audit`)**: Whole-repo ranked architectural audit combining `god_nodes`, `cycles`, `layers`, `dead_code`, `duplicates`, and `debt` into **Must fix / Should fix / Nice to have** findings!
