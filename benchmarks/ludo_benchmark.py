"""Real Ollama Ludo Generation Benchmark: Ponytail vs. Aedile.

Measures `qwen3:4b` generating Ludo engine + UI modules under Ponytail vs. Aedile,
validates syntax via `ast.parse`, and checks architectural integrity via Aedile.
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

PROMPTS = [
    (
        "ludo_engine",
        "Write a clean Python module `ludo_engine.py` using only stdlib (`dataclasses`, `random`) "
        "for a 4-player Ludo game: 52-tile main track, 6-tile home columns, safe star squares, "
        "roll_dice(), valid_moves(), apply_move() with capture & extra turn on 6/capture, and winner check. "
        "Return ONLY valid Python code.",
    ),
    (
        "ludo_ui",
        "Write a clean Python tkinter Canvas module `ludo_ui.py` that imports `ludo_engine` "
        "to render a dark-neon 15x15 Ludo board, animated dice, clickable tokens, and score/turn HUD. "
        "Return ONLY valid Python code.",
    ),
]


def _extract_py(raw: str) -> str:
    m = re.findall(r"```(?:python|py)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if m:
        return max(m, key=len).strip()
    return raw.strip()


def _ollama_gen(model: str, system: str, prompt: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.0, "num_predict": 1400},
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
            "You are a lazy senior developer. Write the smallest complete change. "
            "Prefer stdlib, reuse existing code, no bloat."
        )

    srv = AedileMcpServer(REPO_ROOT)
    aedile_map = srv.handle_map({"budget": 800})["content"][0]["text"]

    out: dict[str, Any] = {"model": model, "modules": {}}
    for mod_name, prompt in PROMPTS:
        consult = srv.handle_consult({"proposed_plan": prompt, "proposed_changes": []})["content"][0]["text"]
        aedile_sys = f"{aedile_map}\n\n{consult}"
        out["modules"][mod_name] = {}

        for tool, sys_p in (("ponytail", ponytail_sys), ("aedile", aedile_sys)):
            print(f"Generating {mod_name} via {tool} ({model})...", flush=True)
            res = _ollama_gen(model, sys_p, prompt)
            code = _extract_py(res["response"])
            ast_ok = False
            ast_err = ""
            try:
                ast.parse(code)
                ast_ok = True
            except SyntaxError as e:
                ast_err = f"L{e.lineno}: {e.msg}"

            out["modules"][mod_name][tool] = {
                "prompt_tokens": res["prompt_tokens"],
                "output_tokens": res["output_tokens"],
                "elapsed_s": res["elapsed_s"],
                "loc": len(code.splitlines()),
                "ast_valid": ast_ok,
                "ast_error": ast_err,
            }
            print(
                f"  -> {tool}/{mod_name}: ast_valid={ast_ok}, loc={len(code.splitlines())}, "
                f"in={res['prompt_tokens']}, out={res['output_tokens']}, time={res['elapsed_s']}s",
                flush=True,
            )

    out_path = os.path.join(REPO_ROOT, "benchmarks", "ludo_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"[OK] Wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
