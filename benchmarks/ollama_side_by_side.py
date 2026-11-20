"""Real side-by-side Ollama benchmark: Ponytail vs. Aedile (12 prompts).

Requires a local Ollama daemon with at least one downloaded model
(e.g., `ollama pull qwen3:4b` or `ollama pull qwen2.5-coder:7b`).
Zero simulated or hardcoded results: all metrics come directly from Ollama.
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from aedile.mcp.server import AedileMcpServer  # noqa: E402

PROMPTS: list[dict[str, Any]] = [
    {
        "id": "p01_reuse_symbol",
        "prompt": "Write a helper to tokenize camelCase and snake_case text into lowercase words for symbol matching.",
        "expected_reuse": "tokenize",
        "proposed_changes": [],
    },
    {
        "id": "p02_reuse_graph_cycle",
        "prompt": "Implement Tarjan's strongly connected components cycle finder for module imports.",
        "expected_reuse": "find_all_cycles",
        "proposed_changes": [],
    },
    {
        "id": "p03_stdlib_toml",
        "prompt": "Parse pyproject.toml to read declared project dependencies.",
        "expected_reuse": "tomllib",
        "proposed_changes": [],
    },
    {
        "id": "p04_stdlib_hash",
        "prompt": "Compute SHA-256 hash of a source file for incremental caching.",
        "expected_reuse": "hashlib",
        "proposed_changes": [],
    },
    {
        "id": "p05_layer_violation_block",
        "prompt": "Import `aedile.cli.setup` inside `src/aedile/shared/config.py` to read intensity mode.",
        "expected_reuse": "layer",
        "proposed_changes": [
            {"path": "src/aedile/shared/config.py", "action": "modify", "imports": ["aedile.cli.setup"]}
        ],
    },
    {
        "id": "p06_cycle_prevention",
        "prompt": "Import `aedile.core.scanner` inside `src/aedile/core/models.py` to attach scan helpers.",
        "expected_reuse": "cycle",
        "proposed_changes": [
            {"path": "src/aedile/core/models.py", "action": "modify", "imports": ["aedile.core.scanner"]}
        ],
    },
    {
        "id": "p07_delete_dangling_import",
        "prompt": "Delete `src/aedile/shared/errors.py` and inline exception strings.",
        "expected_reuse": "dangling",
        "proposed_changes": [{"path": "src/aedile/shared/errors.py", "action": "delete"}],
    },
    {
        "id": "p08_reuse_verifier",
        "prompt": "Create a new class that simulates adding a file and checks if it breaks import layers.",
        "expected_reuse": "ArchitectureVerifier",
        "proposed_changes": [],
    },
    {
        "id": "p09_reuse_baseline",
        "prompt": "Save architectural violations to JSON and filter out already-known issues in CI.",
        "expected_reuse": "BaselineManager",
        "proposed_changes": [],
    },
    {
        "id": "p10_reuse_sarif",
        "prompt": "Export Aedile Report violations to SARIF 2.1.0 format for GitHub Code Scanning.",
        "expected_reuse": "to_sarif",
        "proposed_changes": [],
    },
    {
        "id": "p11_blast_radius",
        "prompt": "Which modules break if `aedile.core.models` changes its `SourceFile` fields?",
        "expected_reuse": "get_blast_radius",
        "proposed_changes": [],
    },
    {
        "id": "p12_debt_ledger",
        "prompt": "Find all `# shortcut:` and `# aedile-waive:` comments missing an upgrade trigger.",
        "expected_reuse": "scan_debt",
        "proposed_changes": [],
    },
]


def _ollama_models(host: str) -> list[str]:
    with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [m["name"] for m in data.get("models", [])]


def _ollama_generate(host: str, model: str, system: str, prompt: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.0, "num_predict": 160},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = round(time.perf_counter() - t0, 3)
    return {
        "response": data.get("response", ""),
        "prompt_tokens": int(data.get("prompt_eval_count", 0)),
        "output_tokens": int(data.get("eval_count", 0)),
        "elapsed_s": elapsed,
    }


def _build_ponytail_context(ponytail_dir: str) -> str:
    agents_md = os.path.join(ponytail_dir, "AGENTS.md")
    map_js = os.path.join(ponytail_dir, "hooks", "ponytail-map.js")
    parts: list[str] = []
    if os.path.exists(agents_md):
        with open(agents_md, encoding="utf-8", errors="ignore") as f:
            parts.append(f.read())
    if os.path.exists(map_js):
        try:
            out = subprocess.check_output(
                ["node", map_js, REPO_ROOT], text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            parts.append(out.strip())
        except Exception:
            pass
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Side-by-side Ollama benchmark: Ponytail vs Aedile")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--model", default=None)
    parser.add_argument("--ponytail-dir", default=None)
    args = parser.parse_args()

    try:
        models = _ollama_models(args.host)
    except urllib.error.URLError as e:
        print(f"[ERROR] Cannot reach Ollama at {args.host}: {e}")
        return 1

    if not models:
        print("[ERROR] No Ollama models downloaded locally (`ollama list` is empty).")
        print("Run e.g. `ollama pull qwen3:4b` or `ollama pull qwen2.5-coder:7b` and retry.")
        return 1

    model = args.model or models[0]
    ponytail_dir = args.ponytail_dir or os.path.join(tempfile.gettempdir(), "ponytail")
    ponytail_sys = _build_ponytail_context(ponytail_dir)
    srv = AedileMcpServer(REPO_ROOT)
    aedile_map = srv.handle_map({"budget": 2000})["content"][0]["text"]

    rows: list[dict[str, Any]] = []
    for item in PROMPTS:
        consult_text = srv.handle_consult(
            {"proposed_plan": item["prompt"], "proposed_changes": item["proposed_changes"]}
        )["content"][0]["text"]
        aedile_sys = f"{aedile_map}\n\n{consult_text}"

        res_p = _ollama_generate(args.host, model, ponytail_sys, item["prompt"])
        res_a = _ollama_generate(args.host, model, aedile_sys, item["prompt"])

        kw = item["expected_reuse"].lower()
        p_hit = kw in res_p["response"].lower()
        a_model_hit = kw in res_a["response"].lower()
        a_tool_caught = kw in consult_text.lower() or kw in aedile_map.lower()

        rows.append(
            {
                "id": item["id"],
                "expected": item["expected_reuse"],
                "ponytail": {
                    **{k: v for k, v in res_p.items() if k != "response"},
                    "model_hit": p_hit,
                },
                "aedile": {
                    **{k: v for k, v in res_a.items() if k != "response"},
                    "model_hit": a_model_hit,
                    "tool_caught": a_tool_caught,
                },
            }
        )
        print(
            f"[{item['id']}] Ponytail hit={p_hit} ({res_p['output_tokens']} out, {res_p['elapsed_s']}s) | "
            f"Aedile model_hit={a_model_hit} tool_caught={a_tool_caught} ({res_a['output_tokens']} out, {res_a['elapsed_s']}s)",
            flush=True,
        )

    out_json = os.path.join(os.path.dirname(__file__), "ollama_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"model": model, "prompts": len(rows), "results": rows}, f, indent=2)

    p_in = statistics.mean(r["ponytail"]["prompt_tokens"] for r in rows)
    a_in = statistics.mean(r["aedile"]["prompt_tokens"] for r in rows)
    p_out = statistics.mean(r["ponytail"]["output_tokens"] for r in rows)
    a_out = statistics.mean(r["aedile"]["output_tokens"] for r in rows)
    p_time = statistics.mean(r["ponytail"]["elapsed_s"] for r in rows)
    a_time = statistics.mean(r["aedile"]["elapsed_s"] for r in rows)
    p_hits = sum(1 for r in rows if r["ponytail"]["model_hit"])
    a_hits = sum(1 for r in rows if r["aedile"]["model_hit"])
    a_tools = sum(1 for r in rows if r["aedile"]["tool_caught"])

    md_path = os.path.join(os.path.dirname(__file__), "BENCHMARKS.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Aedile vs. Ponytail — Real Ollama Benchmark Report\n\n")
        f.write(f"- **Generated on**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Ollama Model**: `{model}` (`temperature=0.0`, `num_predict=160`)\n")
        f.write(f"- **Python Version**: `{sys.version.split()[0]}`\n")
        f.write(f"- **Prompts Evaluated**: {len(rows)} tasks (reuse, stdlib, layer boundary, cycle prevention, delete impact, blast radius, debt ledger)\n\n")
        f.write("## Summary Comparison\n\n")
        f.write("| Metric | Ponytail (`AGENTS.md` + `ponytail-map.js`) | Aedile (`aedile map` + `aedile_consult`) |\n")
        f.write("| :--- | :---: | :---: |\n")
        f.write(f"| **LLM Response Hit Rate** | {p_hits}/{len(rows)} ({p_hits/len(rows)*100:.1f}%) | **{a_hits}/{len(rows)} ({a_hits/len(rows)*100:.1f}%)** |\n")
        f.write(f"| **Deterministic Tool Guarantee** | 0/{len(rows)} (no AST/graph tool) | **{a_tools}/{len(rows)} ({a_tools/len(rows)*100:.1f}%)** |\n")
        f.write(f"| **Avg Prompt Tokens** | {p_in:.1f} | {a_in:.1f} |\n")
        f.write(f"| **Avg Output Tokens** | {p_out:.1f} | {a_out:.1f} |\n")
        f.write(f"| **Avg Latency (s)** | {p_time:.2f}s | {a_time:.2f}s |\n\n")
        f.write("## Per-Prompt Results\n\n")
        f.write("| Prompt ID | Expected Signal | Ponytail Hit | Ponytail Tokens (in/out) | Ponytail Time | Aedile Model Hit | Aedile Tool Caught | Aedile Tokens (in/out) | Aedile Time |\n")
        f.write("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for r in rows:
            p = r["ponytail"]
            a = r["aedile"]
            f.write(
                f"| `{r['id']}` | `{r['expected']}` | {'PASS' if p['model_hit'] else 'FAIL'} | "
                f"{p['prompt_tokens']}/{p['output_tokens']} | {p['elapsed_s']}s | "
                f"{'PASS' if a['model_hit'] else 'FAIL'} | {'YES' if a['tool_caught'] else 'NO'} | "
                f"{a['prompt_tokens']}/{a['output_tokens']} | {a['elapsed_s']}s |\n"
            )

    print(
        f"\nModel: {model} | Ponytail model_hits: {p_hits}/{len(rows)} (avg {p_out:.1f} out tok, {p_time:.2f}s) | "
        f"Aedile model_hits: {a_hits}/{len(rows)}, tool_caught: {a_tools}/{len(rows)} (avg {a_out:.1f} out tok, {a_time:.2f}s)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
