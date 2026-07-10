# Aedile Performance Benchmark Report

**Generated on**: 2026-07-10 13:26:22
**Operating System**: Windows (11)
**Python Version**: 3.14.3
**Processor**: Intel64 Family 6 Model 186 Stepping 2, GenuineIntel

## Task: Add JWT Authentication (10 Runs)

| Configuration | Avg Reasoning (Tokens) | Median | Min | Max | Std Dev | Avg Context (Tokens) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Without Aedile | 1855 | 1865.0 | 1750 | 1940 | 60.23 | 4213 |
| With Aedile | 349 | 350.0 | 330 | 370 | 13.7 | 1200 |

## Task: Add Database Endpoint (10 Runs)

| Configuration | Avg Reasoning (Tokens) | Median | Min | Max | Std Dev | Avg Context (Tokens) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Without Aedile | 1418 | 1415.0 | 1350 | 1480 | 39.94 | 3808 |
| With Aedile | 478 | 480.0 | 450 | 500 | 15.49 | 1347 |

### Key Findings
* **JWT Authentication task**: Reasoning token cost reduced by **81.2%**.
* **Database Endpoint task**: Reasoning token cost reduced by **66.3%**.
