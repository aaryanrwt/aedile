# 4-Way Real LLM Benchmark (`qwen3:4b` via Ollama): Aedile vs RTK vs Ponytail vs Without Anything

Executed live on the **Tesla Roadster Skyline** codebase (`examples/tesla_roadster_game/`) across 6 engineering tasks (24 real Ollama runs).

| Approach | Total Tokens (6 tasks) | Saved vs Baseline | Avg Prompt Tok | Avg Generated LOC | Reuse Hits | Valid Python |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Without Anything | 47,278 | **0 (0.0%)** | 7479.7 | 16.0 | 6/6 | 1/6 |
| Ponytail (AGENTS.md + regex) | 8,020 | **39,258 (83.0%)** | 936.7 | 17.8 | 4/6 | 0/6 |
| RTK (`rtk-ai/rtk` log compression) | 42,658 | **4,620 (9.8%)** | 6709.7 | 13.0 | 5/6 | 1/6 |
| **Aedile (AST/Graph + Consult + Compress)** | 3,418 | **43,860 (92.8%)** | 169.7 | 18.7 | 4/6 | 0/6 |
