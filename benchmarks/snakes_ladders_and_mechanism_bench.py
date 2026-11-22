"""Real Ollama Snakes & Ladders + Core Mechanism Benchmark: Ponytail vs. Aedile.

Tests two things with local `qwen3:4b` (zero faking):
1. Snakes & Ladders module generation (`snakes_engine`, `snakes_ui`) under Ponytail vs. Aedile.
2. Core mechanism ("Before an AI writes code, prove it deserves to exist"):
   6 adversarial prompts where code/dependencies already exist or violate architecture.
"""

import ast
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from aedile.mcp.server import AedileMcpServer  # noqa: E402

GAME_PROMPTS = [
    (
        "snakes_engine",
        "Write a Python module `snakes_engine.py` using only stdlib (`dataclasses`, `random`) "
        "for a 10x10 Snakes & Ladders game (tiles 1..100, snake/ladder jump map, exact-100 win, "
        "bonus turn on 6). Return ONLY valid Python code.",
    ),
    (
        "snakes_ui",
        "Write a Python tkinter Canvas module `snakes_ui.py` importing `snakes_engine` "
        "to render a 10x10 boustrophedon Snakes & Ladders board, curved snakes, ladders, "
        "animated dice, and player tokens. Return ONLY valid Python code.",
    ),
]

MECHANISM_TESTS: list[dict[str, Any]] = [
    {
        "id": "mech_01_yagni_duplicate_cache",
        "prompt": "Write a brand new JSON file cache class `FileScanCache` from scratch with load/save/get/set.",
        "expected": "ScanCache",
        "changes": [],
    },
    {
        "id": "mech_02_reuse_mapper",
        "prompt": "Create a new function `generate_repo_symbol_map` to list public symbols per directory within 2000 chars.",
        "expected": "build_codebase_map",
        "changes": [],
    },
    {
        "id": "mech_03_stdlib_sqlite",
        "prompt": "Implement a custom local embedded SQLite storage wrapper without using Python's built-in modules.",
        "expected": "sqlite3",
        "changes": [],
    },
    {
        "id": "mech_04_block_layer_violation",
        "prompt": "Add `import aedile.mcp.server` inside `src/aedile/core/models.py`.",
        "expected": "layer",
        "changes": [
            {
                "path": "src/aedile/core/models.py",
                "action": "modify",
                "imports": ["aedile.mcp.server"],
            }
        ],
    },
    {
        "id": "mech_05_block_cycle",
        "prompt": "Import `aedile.core.scanner` inside `src/aedile/core/graph.py`.",
        "expected": "cycle",
        "changes": [
            {
                "path": "src/aedile/core/graph.py",
                "action": "modify",
                "imports": ["aedile.core.scanner"],
            }
        ],
    },
    {
        "id": "mech_06_block_unsafe_delete",
        "prompt": "Delete `src/aedile/core/models.py` since we want to inline dataclasses.",
        "expected": "dangling",
        "changes": [{"path": "src/aedile/core/models.py", "action": "delete"}],
    },
]


def _extract_py(raw: str) -> str:
    m = re.findall(r"```(?:python|py)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if m:
        return max(m, key=len).strip()
    return raw.strip()


def _ollama_gen(model: str, system: str, prompt: str, num_predict: int) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.0, "num_predict": num_predict},
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
    ponytail_agents = os.path.join(tempfile.gettempdir(), "ponytail", "AGENTS.md")
    if os.path.exists(ponytail_agents):
        with open(ponytail_agents, encoding="utf-8") as f:
            ponytail_sys = f.read()
    else:
        ponytail_sys = (
            "You are a lazy senior developer. The best code is the code never written. "
            "Reuse existing codebase helpers and stdlib before writing new code."
        )

    srv = AedileMcpServer(REPO_ROOT)
    aedile_map = srv.handle_map({"budget": 900})["content"][0]["text"]

    results: dict[str, Any] = {"model": model, "game_generation": {}, "core_mechanism": []}

    # 1. Snakes & Ladders generation benchmark
    for mod_name, prompt in GAME_PROMPTS:
        consult = srv.handle_consult({"proposed_plan": prompt, "proposed_changes": []})["content"][
            0
        ]["text"]
        aedile_sys = f"{aedile_map}\n\n{consult}"
        results["game_generation"][mod_name] = {}

        for tool, sys_p in (("ponytail", ponytail_sys), ("aedile", aedile_sys)):
            print(f"[Game] {mod_name} via {tool}...", flush=True)
            res = _ollama_gen(model, sys_p, prompt, num_predict=1400)
            code = _extract_py(res["response"])
            ast_ok = False
            try:
                ast.parse(code)
                ast_ok = True
            except SyntaxError:
                pass
            results["game_generation"][mod_name][tool] = {
                "prompt_tokens": res["prompt_tokens"],
                "output_tokens": res["output_tokens"],
                "elapsed_s": res["elapsed_s"],
                "loc": len(code.splitlines()),
                "ast_valid": ast_ok,
            }

    # 2. Core mechanism ("prove code deserves to exist") benchmark
    for item in MECHANISM_TESTS:
        consult = srv.handle_consult(
            {"proposed_plan": item["prompt"], "proposed_changes": item["changes"]}
        )["content"][0]["text"]
        aedile_sys = f"{aedile_map}\n\n{consult}"

        res_p = _ollama_gen(model, ponytail_sys, item["prompt"], num_predict=160)
        res_a = _ollama_gen(model, aedile_sys, item["prompt"], num_predict=160)

        kw = item["expected"].lower()
        p_hit = kw in res_p["response"].lower()
        a_hit = kw in res_a["response"].lower()
        a_tool = kw in consult.lower() or kw in aedile_map.lower()

        results["core_mechanism"].append(
            {
                "id": item["id"],
                "expected": item["expected"],
                "ponytail": {
                    "prompt_tokens": res_p["prompt_tokens"],
                    "output_tokens": res_p["output_tokens"],
                    "elapsed_s": res_p["elapsed_s"],
                    "model_caught": p_hit,
                },
                "aedile": {
                    "prompt_tokens": res_a["prompt_tokens"],
                    "output_tokens": res_a["output_tokens"],
                    "elapsed_s": res_a["elapsed_s"],
                    "model_caught": a_hit,
                    "tool_caught": a_tool,
                },
            }
        )
        print(
            f"[Mech] {item['id']}: Ponytail={p_hit} ({res_p['prompt_tokens']} in) | "
            f"Aedile model={a_hit}, tool={a_tool} ({res_a['prompt_tokens']} in)",
            flush=True,
        )

    out_json = os.path.join(REPO_ROOT, "benchmarks", "snakes_ladders_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"[OK] Saved {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
