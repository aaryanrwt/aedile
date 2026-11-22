# 4-Way Cyber-Roadster 3D Executable Comparison (`qwen3:4b` via Ollama)

All 4 standalone Windows executables (`examples/tesla_roadster_4way/dist/*.exe`) were built with `PyInstaller` and smoke-tested for clean launch.

| Approach | Executable | Size | Launch OK | Prompt Tok | Total Tok | Saved vs Baseline | Gen LOC | Valid AI Hook |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Without Anything | `Roadster_WithoutAnything.exe` | 13.02 MB | True | 6,430 | 7,630 | **0 (0.0%)** | 0 | False |
| Ponytail | `Roadster_Ponytail.exe` | 13.02 MB | True | 858 | 1,756 | **5,874 (77.0%)** | 5 | True |
| RTK (rtk-ai/rtk) | `Roadster_RTK.exe` | 13.02 MB | True | 5,746 | 6,946 | **684 (9.0%)** | 0 | False |
| Aedile | `Roadster_Aedile.exe` | 13.02 MB | True | 189 | 1,389 | **6,241 (81.8%)** | 0 | False |
