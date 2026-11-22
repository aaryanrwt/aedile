# Full-Application 3-Way Bakeoff (`qwen3:4b`): Baseline vs. Ponytail vs. Aedile

Built a 4-file Expense & Budget Tracker (`storage/repo.py`, `analytics/summary.py`, `cli/app.py`, `tests/test_app.py`) on top of a seeded repo (`src/shared/db.py`, `src/shared/models.py`, `aedile.toml`). Temporary app workspaces were deleted after verification.

| Metric | Baseline (No Tool) | Ponytail | Aedile |
| :--- | :---: | :---: | :---: |
| **Total Generated LOC** | 168 | 99 | 88 |
| **Total Prompt Tokens** | 329 | 393 | 1268 |
| **Total Output Tokens** | 2600 | 2600 | 2600 |
| **AST-Valid Files** | 0/4 | 0/4 | 0/4 |
| **Reused `shared.db`** | False | False | False |
| **Reused `shared.models`** | False | False | False |
| **Architecture Errors** | 0 | 0 | 0 |
| **`pytest` Passed** | False | False | False |
| **Total Time (s)** | 73.67s | 74.02s | 76.13s |
