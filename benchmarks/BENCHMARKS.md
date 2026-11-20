# Aedile vs. Ponytail — Real Ollama Benchmark Report

- **Generated on**: 2026-11-20 17:57:42
- **Ollama Model**: `qwen3:4b` (`temperature=0.0`, `num_predict=160`)
- **Python Version**: `3.15.2`
- **Prompts Evaluated**: 12 tasks (reuse, stdlib, layer boundary, cycle prevention, delete impact, blast radius, debt ledger)

## Summary Comparison

| Metric | Ponytail (`AGENTS.md` + `ponytail-map.js`) | Aedile (`aedile map` + `aedile_consult`) |
| :--- | :---: | :---: |
| **LLM Response Hit Rate** | 2/12 (16.7%) | **10/12 (83.3%)** |
| **Deterministic Tool Guarantee** | 0/12 (no AST/graph tool) | **11/12 (91.7%)** |
| **Avg Prompt Tokens** | 794.6 | 752.8 |
| **Avg Output Tokens** | 160.0 | 160.0 |
| **Avg Latency (s)** | 5.44s | 5.76s |

## Per-Prompt Results

| Prompt ID | Expected Signal | Ponytail Hit | Ponytail Tokens (in/out) | Ponytail Time | Aedile Model Hit | Aedile Tool Caught | Aedile Tokens (in/out) | Aedile Time |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `p01_reuse_symbol` | `tokenize` | PASS | 795/160 | 5.55s | PASS | YES | 528/160 | 5.727s |
| `p02_reuse_graph_cycle` | `find_all_cycles` | FAIL | 790/160 | 5.374s | PASS | YES | 525/160 | 5.642s |
| `p03_stdlib_toml` | `tomllib` | FAIL | 788/160 | 5.433s | PASS | YES | 973/160 | 6.114s |
| `p04_stdlib_hash` | `hashlib` | PASS | 792/160 | 5.359s | PASS | YES | 938/160 | 5.827s |
| `p05_layer_violation_block` | `layer` | FAIL | 799/160 | 5.421s | PASS | YES | 1019/160 | 5.84s |
| `p06_cycle_prevention` | `cycle` | FAIL | 800/160 | 5.595s | PASS | YES | 1063/160 | 5.986s |
| `p07_delete_dangling_import` | `dangling` | FAIL | 792/160 | 5.47s | PASS | YES | 903/160 | 6.074s |
| `p08_reuse_verifier` | `ArchitectureVerifier` | FAIL | 795/160 | 5.521s | PASS | YES | 542/160 | 5.616s |
| `p09_reuse_baseline` | `BaselineManager` | FAIL | 791/160 | 5.322s | PASS | YES | 674/160 | 5.505s |
| `p10_reuse_sarif` | `to_sarif` | FAIL | 799/160 | 5.374s | PASS | YES | 623/160 | 5.473s |
| `p11_blast_radius` | `get_blast_radius` | FAIL | 795/160 | 5.32s | FAIL | NO | 620/160 | 5.589s |
| `p12_debt_ledger` | `scan_debt` | FAIL | 799/160 | 5.519s | FAIL | YES | 626/160 | 5.679s |
