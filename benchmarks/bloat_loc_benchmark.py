"""10-Task A/B Bloat & LOC Benchmark on local Ollama (`qwen3:4b`): No Aedile vs. With Aedile.

Measures actual generated Python Lines of Code (LOC), output tokens, and reuse rate
on tasks that only require 1-5 lines when reusing existing repo helpers or stdlib.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import urllib.request
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from aedile.mcp.server import AedileMcpServer  # noqa: E402

TASKS: list[dict[str, str]] = [
    {
        "id": "t01_toml_deps",
        "prompt": "Write a Python snippet to parse pyproject.toml dependencies.",
        "expected": "tomllib",
    },
    {
        "id": "t02_sha256_hash",
        "prompt": "Write a Python function to compute the SHA-256 hex digest of a file's bytes.",
        "expected": "hashlib",
    },
    {
        "id": "t03_tokenize_symbol",
        "prompt": "Write Python code to tokenize camelCase and snake_case symbol names into lowercase words.",
        "expected": "tokenize",
    },
    {
        "id": "t04_scan_cache",
        "prompt": "Write Python code to load and query the incremental file scan cache by file hash.",
        "expected": "ScanCache",
    },
    {
        "id": "t05_cycle_finder",
        "prompt": "Write Python code to detect all circular module dependencies in the architecture graph.",
        "expected": "find_all_cycles",
    },
    {
        "id": "t06_codebase_map",
        "prompt": "Write Python code to build a 2000-character symbol map of the codebase.",
        "expected": "build_codebase_map",
    },
    {
        "id": "t07_sarif_export",
        "prompt": "Write Python code to export an Aedile Report into SARIF 2.1.0 JSON.",
        "expected": "to_sarif",
    },
    {
        "id": "t08_baseline_filter",
        "prompt": "Write Python code to filter out already-baselined architectural violations.",
        "expected": "BaselineManager",
    },
    {
        "id": "t09_blast_radius",
        "prompt": "Write Python code to find all transitive dependent modules affected by editing a module.",
        "expected": "get_blast_radius",
    },
    {
        "id": "t10_debt_scan",
        "prompt": "Write Python code to scan the repo for `# shortcut:` comments without upgrade triggers.",
        "expected": "scan_debt",
    },
]


def _extract_code_loc(raw: str) -> tuple[str, int]:
    blocks = re.findall(r"```(?:python|py)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    code = max(blocks, key=len).strip() if blocks else raw.strip()
    loc = sum(1 for line in code.splitlines() if line.strip() and not line.strip().startswith("#"))
    return code, loc


def _ollama_gen(model: str, system: str, prompt: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt + "\nOutput ONLY concise Python code.",
            "stream": False,
            "think": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.0, "num_predict": 400},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        "response": data.get("response", ""),
        "prompt_tokens": int(data.get("prompt_eval_count", 0)),
        "output_tokens": int(data.get("eval_count", 0)),
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }


def main() -> int:
    model = "qwen3:4b"
    baseline_sys = "You are a Python developer working in the Aedile repository."
    srv = AedileMcpServer(REPO_ROOT)
    aedile_map = srv.handle_map({"budget": 1000})["content"][0]["text"]

    rows: list[dict[str, Any]] = []
    for task in TASKS:
        consult = srv.handle_consult({"proposed_plan": task["prompt"], "proposed_changes": []})[
            "content"
        ][0]["text"]
        aedile_sys = (
            "You are a Python developer working in Aedile. Reuse existing symbols or stdlib "
            "identified below instead of rewriting them.\n\n"
            f"{aedile_map}\n\n{consult}"
        )

        res_base = _ollama_gen(model, baseline_sys, task["prompt"])
        res_aed = _ollama_gen(model, aedile_sys, task["prompt"])

        _, base_loc = _extract_code_loc(res_base["response"])
        _, aed_loc = _extract_code_loc(res_aed["response"])
        kw = task["expected"].lower()
        base_reused = kw in res_base["response"].lower()
        aed_reused = kw in res_aed["response"].lower()

        rows.append(
            {
                "id": task["id"],
                "expected": task["expected"],
                "no_aedile": {
                    "loc": base_loc,
                    "prompt_tokens": res_base["prompt_tokens"],
                    "output_tokens": res_base["output_tokens"],
                    "elapsed_s": res_base["elapsed_s"],
                    "reused": base_reused,
                },
                "with_aedile": {
                    "loc": aed_loc,
                    "prompt_tokens": res_aed["prompt_tokens"],
                    "output_tokens": res_aed["output_tokens"],
                    "elapsed_s": res_aed["elapsed_s"],
                    "reused": aed_reused,
                },
            }
        )
        print(
            f"[{task['id']}] No-Aedile: {base_loc} LOC, {res_base['output_tokens']} out, reused={base_reused} | "
            f"With-Aedile: {aed_loc} LOC, {res_aed['output_tokens']} out, reused={aed_reused}",
            flush=True,
        )

    avg_base_loc = statistics.mean(r["no_aedile"]["loc"] for r in rows)
    avg_aed_loc = statistics.mean(r["with_aedile"]["loc"] for r in rows)
    avg_base_out = statistics.mean(r["no_aedile"]["output_tokens"] for r in rows)
    avg_aed_out = statistics.mean(r["with_aedile"]["output_tokens"] for r in rows)
    base_reuse = sum(1 for r in rows if r["no_aedile"]["reused"])
    aed_reuse = sum(1 for r in rows if r["with_aedile"]["reused"])

    out_json = os.path.join(REPO_ROOT, "benchmarks", "bloat_loc_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": model,
                "summary": {
                    "avg_loc_no_aedile": round(avg_base_loc, 1),
                    "avg_loc_with_aedile": round(avg_aed_loc, 1),
                    "avg_output_tokens_no_aedile": round(avg_base_out, 1),
                    "avg_output_tokens_with_aedile": round(avg_aed_out, 1),
                    "reuse_rate_no_aedile": f"{base_reuse}/{len(rows)}",
                    "reuse_rate_with_aedile": f"{aed_reuse}/{len(rows)}",
                },
                "tasks": rows,
            },
            f,
            indent=2,
        )

    md_path = os.path.join(REPO_ROOT, "benchmarks", "BLOAT_LOC_BENCHMARK.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Aedile Bloat & Lines-of-Code (LOC) Benchmark (`qwen3:4b`)\n\n")
        f.write("## Summary (10 Tasks, No Aedile vs. With Aedile)\n\n")
        f.write("| Metric | Without Aedile | With Aedile |\n")
        f.write("| :--- | :---: | :---: |\n")
        f.write(f"| **Avg Generated LOC** | {avg_base_loc:.1f} | **{avg_aed_loc:.1f}** |\n")
        f.write(f"| **Avg Output Tokens** | {avg_base_out:.1f} | **{avg_aed_out:.1f}** |\n")
        f.write(
            f"| **Codebase / Stdlib Reuse** | {base_reuse}/{len(rows)} | **{aed_reuse}/{len(rows)}** |\n\n"
        )
        f.write("## Per-Task Breakdown\n\n")
        f.write(
            "| Task | Target Symbol/Stdlib | No-Aedile LOC (Out Tok / Reused) | With-Aedile LOC (Out Tok / Reused) |\n"
        )
        f.write("| :--- | :--- | :---: | :---: |\n")
        for r in rows:
            b = r["no_aedile"]
            a = r["with_aedile"]
            f.write(
                f"| `{r['id']}` | `{r['expected']}` | "
                f"{b['loc']} LOC ({b['output_tokens']} tok, {'YES' if b['reused'] else 'NO'}) | "
                f"**{a['loc']} LOC** ({a['output_tokens']} tok, {'YES' if a['reused'] else 'NO'}) |\n"
            )
    print(
        f"\nSUMMARY: LOC {avg_base_loc:.1f} -> {avg_aed_loc:.1f} | "
        f"Out Tok {avg_base_out:.1f} -> {avg_aed_out:.1f} | Reuse {base_reuse}/10 -> {aed_reuse}/10",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
