# Aedile Token Savings & Pre-Write Gate Benchmark (55 Real-World Tests)

## Summary

| Suite | Tests | Baseline Tokens | Aedile Tokens | Tokens Saved | Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **CLI Output Compression** (`aedile compress`) | 30 | 82,411 | 19,982 | **62,429** | **75.8%** |
| **Pre-Write Gate** (`aedile_consult` + `verify`) | 25 | 807,570 | 462 | **807,108** | **99.9%** |
| **Combined Total** | **55** | **889,981** | **20,444** | **869,537** | **97.7%** |

## All 55 Test Runs

| # | Category | Test | Filter / Check | Baseline Tok | Aedile Tok | Saved | Reduction | Time |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | `cli_compression` | pytest: test_mcp | `pytest` | 446 | 4 | 442 | **99.1%** | 5257.0ms |
| 2 | `cli_compression` | pytest: test_v1_1_buffs | `pytest` | 522 | 4 | 518 | **99.2%** | 2156.4ms |
| 3 | `cli_compression` | pytest: test_graph | `pytest` | 340 | 340 | 0 | **0.0%** | 1685.0ms |
| 4 | `cli_compression` | pytest: test_scanner | `pytest` | 341 | 340 | 1 | **0.3%** | 1559.3ms |
| 5 | `cli_compression` | pytest: test_rules | `pytest` | 426 | 4 | 422 | **99.1%** | 1667.6ms |
| 6 | `cli_compression` | pytest: test_cli | `pytest` | 340 | 339 | 1 | **0.3%** | 1434.5ms |
| 7 | `cli_compression` | pytest: test_verifier | `pytest` | 341 | 340 | 1 | **0.3%** | 1489.1ms |
| 8 | `cli_compression` | pytest: test_baseline | `pytest` | 341 | 340 | 1 | **0.3%** | 1502.2ms |
| 9 | `cli_compression` | pytest: test_polyglot | `pytest` | 341 | 340 | 1 | **0.3%** | 1568.1ms |
| 10 | `cli_compression` | pytest: full suite | `pytest` | 27,339 | 5 | 27,334 | **100.0%** | 10461.1ms |
| 11 | `cli_compression` | git: log -n 25 | `generic` | 3,830 | 540 | 3,290 | **85.9%** | 384.6ms |
| 12 | `cli_compression` | git: log -n 50 oneline | `generic` | 313 | 313 | 0 | **0.0%** | 79.0ms |
| 13 | `cli_compression` | git: diff HEAD~1..HEAD | `git_diff` | 374 | 361 | 13 | **3.5%** | 104.3ms |
| 14 | `cli_compression` | git: diff HEAD~3..HEAD | `git_diff` | 560 | 457 | 103 | **18.4%** | 105.7ms |
| 15 | `cli_compression` | git: diff HEAD~5..HEAD | `git_diff` | 33,710 | 11,085 | 22,625 | **67.1%** | 94.4ms |
| 16 | `cli_compression` | git: show HEAD~1 | `generic` | 256 | 254 | 2 | **0.8%** | 98.9ms |
| 17 | `cli_compression` | git: status -v | `generic` | 189 | 188 | 1 | **0.5%** | 73.0ms |
| 18 | `cli_compression` | git: ls-files | `generic` | 609 | 271 | 338 | **55.5%** | 62.0ms |
| 19 | `cli_compression` | ruff: check . | `ruff_mypy` | 4 | 4 | 0 | **0.0%** | 2556.9ms |
| 20 | `cli_compression` | ruff: check --statistics | `ruff_mypy` | 0 | 0 | 0 | **0.0%** | 260.0ms |
| 21 | `cli_compression` | mypy: src/ | `ruff_mypy` | 11 | 10 | 1 | **9.1%** | 1496.0ms |
| 22 | `cli_compression` | aedile: check | `generic` | 1,389 | 1,389 | 0 | **0.0%** | 432.7ms |
| 23 | `cli_compression` | aedile: audit | `generic` | 2,074 | 791 | 1,283 | **61.9%** | 623.6ms |
| 24 | `cli_compression` | aedile: insights | `generic` | 146 | 146 | 0 | **0.0%** | 376.9ms |
| 25 | `cli_compression` | aedile: doctor | `generic` | 153 | 153 | 0 | **0.0%** | 391.2ms |
| 26 | `cli_compression` | aedile: map 2000 | `generic` | 240 | 240 | 0 | **0.0%** | 464.9ms |
| 27 | `cli_compression` | aedile: map 800 | `generic` | 244 | 243 | 1 | **0.4%** | 413.0ms |
| 28 | `cli_compression` | aedile: debt | `generic` | 20 | 20 | 0 | **0.0%** | 334.8ms |
| 29 | `cli_compression` | aedile: graph mermaid | `generic` | 1,920 | 460 | 1,460 | **76.0%** | 438.1ms |
| 30 | `cli_compression` | aedile: graph svg | `generic` | 5,592 | 1,001 | 4,591 | **82.1%** | 640.6ms |
| 31 | `prewrite_consult` | consult: Tarjan cycle detection | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 4.2ms |
| 32 | `prewrite_consult` | consult: BM25 symbol search | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.1ms |
| 33 | `prewrite_consult` | consult: AST codebase map | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.0ms |
| 34 | `prewrite_consult` | consult: Telemetry store | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.4ms |
| 35 | `prewrite_consult` | consult: SARIF report export | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.4ms |
| 36 | `prewrite_consult` | consult: cProfile hotspots | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.5ms |
| 37 | `prewrite_consult` | consult: Community detection | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.5ms |
| 38 | `prewrite_consult` | consult: Layer inference | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.4ms |
| 39 | `prewrite_consult` | consult: Monorepo boundaries | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.5ms |
| 40 | `prewrite_consult` | consult: Baseline ratchet | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.6ms |
| 41 | `prewrite_consult` | consult: Stdlib JSON parser | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.0ms |
| 42 | `prewrite_consult` | consult: Stdlib SHA-256 hash | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 0.9ms |
| 43 | `prewrite_consult` | consult: Stdlib HTTP server | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.1ms |
| 44 | `prewrite_consult` | consult: Output compressor | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.3ms |
| 45 | `prewrite_consult` | consult: Debt ledger scan | `prewrite_consult` | 52,838 | 9 | 52,829 | **100.0%** | 1.6ms |
| 46 | `prewrite_verify` | verify: valid leaf helper | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 90.8ms |
| 47 | `prewrite_verify` | verify: valid core module | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 77.6ms |
| 48 | `prewrite_verify` | verify: valid cli helper | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 77.7ms |
| 49 | `prewrite_verify` | verify: valid infra cache | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 68.9ms |
| 50 | `prewrite_verify` | verify: valid mcp helper | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 88.8ms |
| 51 | `prewrite_verify` | verify: catch shared->core layer violation | `prewrite_verify` | 1,500 | 88 | 1,412 | **94.1%** | 72.7ms |
| 52 | `prewrite_verify` | verify: catch core->cli layer violation | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 60.6ms |
| 53 | `prewrite_verify` | verify: catch core->mcp layer violation | `prewrite_verify` | 1,500 | 9 | 1,491 | **99.4%** | 57.1ms |
| 54 | `prewrite_verify` | verify: catch shared->infra violation | `prewrite_verify` | 1,500 | 90 | 1,410 | **94.0%** | 64.8ms |
| 55 | `prewrite_verify` | verify: catch circular self/core cycle | `prewrite_verify` | 1,500 | 86 | 1,414 | **94.3%** | 54.8ms |
