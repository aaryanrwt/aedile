# Aedile Bloat & Lines-of-Code (LOC) Benchmark (`qwen3:4b`)

## Summary (10 Tasks, No Aedile vs. With Aedile)

| Metric | Without Aedile | With Aedile |
| :--- | :---: | :---: |
| **Avg Generated LOC** | 19.6 | **9.9** |
| **Avg Output Tokens** | 400.0 | **400.0** |
| **Codebase / Stdlib Reuse** | 2/10 | **10/10** |

## Per-Task Breakdown

| Task | Target Symbol/Stdlib | No-Aedile LOC (Out Tok / Reused) | With-Aedile LOC (Out Tok / Reused) |
| :--- | :--- | :---: | :---: |
| `t01_toml_deps` | `tomllib` | 18 LOC (400 tok, NO) | **12 LOC** (400 tok, YES) |
| `t02_sha256_hash` | `hashlib` | 29 LOC (400 tok, YES) | **10 LOC** (400 tok, YES) |
| `t03_tokenize_symbol` | `tokenize` | 21 LOC (400 tok, YES) | **10 LOC** (400 tok, YES) |
| `t04_scan_cache` | `ScanCache` | 21 LOC (400 tok, NO) | **9 LOC** (400 tok, YES) |
| `t05_cycle_finder` | `find_all_cycles` | 20 LOC (400 tok, NO) | **11 LOC** (400 tok, YES) |
| `t06_codebase_map` | `build_codebase_map` | 12 LOC (400 tok, NO) | **12 LOC** (400 tok, YES) |
| `t07_sarif_export` | `to_sarif` | 21 LOC (400 tok, NO) | **11 LOC** (400 tok, YES) |
| `t08_baseline_filter` | `BaselineManager` | 20 LOC (400 tok, NO) | **13 LOC** (400 tok, YES) |
| `t09_blast_radius` | `get_blast_radius` | 20 LOC (400 tok, NO) | **5 LOC** (400 tok, YES) |
| `t10_debt_scan` | `scan_debt` | 14 LOC (400 tok, NO) | **6 LOC** (400 tok, YES) |
