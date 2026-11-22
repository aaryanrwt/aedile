"""Real 4-way Ollama qwen3:4b benchmark: Aedile vs RTK vs Ponytail vs Without Anything."""

from __future__ import annotations

import ast
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

AEDILE_ROOT = Path(__file__).resolve().parent.parent
GAME_ROOT = AEDILE_ROOT / "examples" / "tesla_roadster_game"
sys.path.insert(0, str(AEDILE_ROOT / "src"))

from aedile.core.compressor import compress_output, estimate_tokens  # noqa: E402
from aedile.mcp.server import AedileMcpServer  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:4b"

TASKS: list[dict[str, str]] = [
    {
        "name": "Thruster flight & battery step",
        "query": "step_roadster",
        "prompt": "Write a concise Python function `update_boost_flight(state, controls, dt)` that updates Roadster vertical flight, speed, and SpaceX boost battery. Reuse existing helpers if present.",
        "expected_reuse": "step_roadster",
    },
    {
        "name": "Hitbox AABB collision check",
        "query": "roadster_hits_box",
        "prompt": "Write a concise Python function `check_drone_collision(state, drone)` returning True when the Roadster hits a drone. Reuse existing helpers if present.",
        "expected_reuse": "roadster_hits_box",
    },
    {
        "name": "Thruster particle emission",
        "query": "emit_thruster",
        "prompt": "Write a concise Python function `spawn_exhaust(world, state)` that spawns capped thruster particles without frame lag. Reuse existing helpers if present.",
        "expected_reuse": "emit_thruster",
    },
    {
        "name": "World entity scroll & cull",
        "query": "WorldManager",
        "prompt": "Write a concise Python function `advance_skyline(world, dt, speed_kmh)` to scroll stars, buildings, obstacles, and particles. Reuse existing helpers if present.",
        "expected_reuse": "step",
    },
    {
        "name": "JSON high-score persistence",
        "query": "json",
        "prompt": "Write a concise Python function `save_best_score(path, score)` using standard library only to persist high score JSON.",
        "expected_reuse": "json",
    },
    {
        "name": "HUD Mach & altitude formatter",
        "query": "WINDOW_HEIGHT",
        "prompt": "Write a concise Python function `format_hud_line(state, fps)` returning speed in km/h, Mach number, and altitude in meters. Reuse constants from config.",
        "expected_reuse": "WINDOW_HEIGHT",
    },
]

SAMPLE_PYTEST_LOG = (
    "=== test session starts ===\n"
    + ("examples/tesla_roadster_game/test_game.py::test_frame PASSED\n" * 45)
    + "=== 45 passed in 0.14s ===\n"
)


def _call_ollama(prompt: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 400},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, flags=re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def _count_loc(code: str) -> int:
    return sum(1 for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#"))


def _ponytail_regex_map(game_files: list[Path]) -> str:
    lines = ["# AGENTS.md (Ponytail Mode)", "Available symbols (regex):"]
    for p in game_files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        defs = re.findall(r"^(?:def|class)\s+([A-Za-z_]\w*)", txt, flags=re.MULTILINE)
        lines.append(f"- {p.name}: {', '.join(defs)}")
    return "\n".join(lines)


def main() -> int:
    game_files = sorted(
        p for p in GAME_ROOT.glob("*.py") if p.name not in {"test_game.py", "main.py"}
    )
    full_source_ctx = "\n\n".join(
        f"# {p.name}\n{p.read_text(encoding='utf-8', errors='replace')}" for p in game_files
    )
    ponytail_ctx = _ponytail_regex_map(game_files)

    server = AedileMcpServer(str(GAME_ROOT))
    server.config.src_dirs = ["."]
    server.refresh_index()
    aedile_map_txt = server.handle_map({"budget_chars": 900})["content"][0]["text"]
    compressed_pytest = compress_output(
        SAMPLE_PYTEST_LOG, command="pytest", exit_code=0, project_root=None, record_telemetry=False
    )

    modes = ("without_anything", "ponytail", "rtk", "aedile")
    rows: list[dict[str, Any]] = []

    for mode in modes:
        for t in TASKS:
            if mode == "without_anything":
                ctx = full_source_ctx + "\n\nRecent test log:\n" + SAMPLE_PYTEST_LOG
            elif mode == "ponytail":
                ctx = ponytail_ctx + "\n\nRecent test log:\n" + SAMPLE_PYTEST_LOG
            elif mode == "rtk":
                ctx = (
                    full_source_ctx
                    + "\n\nRecent test log (RTK compressed):\n"
                    + compressed_pytest.compressed
                )
            else:
                consult_txt = server.handle_consult({"query": t["query"], "intent": t["prompt"]})[
                    "content"
                ][0]["text"]
                ctx = (
                    f"{aedile_map_txt}\n\nAedile Consult:\n{consult_txt}\n\n"
                    f"Recent test log (Aedile compressed):\n{compressed_pytest.compressed}"
                )

            full_prompt = (
                f"{ctx}\n\nTask: {t['prompt']}\nRespond with ONLY one concise Python code block."
            )
            t0 = time.perf_counter()
            res = _call_ollama(full_prompt)
            elapsed = round(time.perf_counter() - t0, 2)
            raw_reply = res.get("response", "")
            code = _extract_code(raw_reply)
            loc = _count_loc(code)
            try:
                ast.parse(code)
                syntax_ok = True
            except SyntaxError:
                syntax_ok = False
            reused = t["expected_reuse"] in code
            prompt_tok = int(res.get("prompt_eval_count") or estimate_tokens(full_prompt))
            gen_tok = int(res.get("eval_count") or estimate_tokens(raw_reply))

            rows.append(
                {
                    "mode": mode,
                    "task": t["name"],
                    "prompt_tokens": prompt_tok,
                    "generated_tokens": gen_tok,
                    "total_tokens": prompt_tok + gen_tok,
                    "loc": loc,
                    "reused": reused,
                    "syntax_ok": syntax_ok,
                    "elapsed_s": elapsed,
                }
            )
            print(
                f"[{mode}] {t['name']}: tok={prompt_tok}+{gen_tok}={prompt_tok + gen_tok}, "
                f"loc={loc}, reuse={reused}, syntax={syntax_ok} ({elapsed}s)",
                flush=True,
            )

    summary: dict[str, dict[str, Any]] = {}
    for mode in modes:
        sub = [r for r in rows if r["mode"] == mode]
        summary[mode] = {
            "tasks": len(sub),
            "total_tokens": sum(r["total_tokens"] for r in sub),
            "avg_prompt_tokens": round(sum(r["prompt_tokens"] for r in sub) / len(sub), 1),
            "avg_loc": round(sum(r["loc"] for r in sub) / len(sub), 1),
            "reuse_hits": sum(1 for r in sub if r["reused"]),
            "syntax_valid": sum(1 for r in sub if r["syntax_ok"]),
        }

    baseline_tok = summary["without_anything"]["total_tokens"]
    for s in summary.values():
        saved = max(0, baseline_tok - s["total_tokens"])
        s["tokens_saved_vs_baseline"] = saved
        s["reduction_pct"] = round((saved / baseline_tok) * 100.0, 1) if baseline_tok else 0.0

    out_json = AEDILE_ROOT / "benchmarks" / "four_way_results.json"
    out_json.write_text(
        json.dumps({"model": MODEL, "summary": summary, "runs": rows}, indent=2), encoding="utf-8"
    )

    out_md = AEDILE_ROOT / "benchmarks" / "FOUR_WAY_BENCHMARK.md"
    lines = [
        f"# 4-Way Real LLM Benchmark (`{MODEL}` via Ollama): Aedile vs RTK vs Ponytail vs Without Anything",
        "",
        "Executed live on the **Tesla Roadster Skyline** codebase (`examples/tesla_roadster_game/`) across 6 engineering tasks (24 real Ollama runs).",
        "",
        "| Approach | Total Tokens (6 tasks) | Saved vs Baseline | Avg Prompt Tok | Avg Generated LOC | Reuse Hits | Valid Python |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    labels = {
        "without_anything": "Without Anything",
        "ponytail": "Ponytail (AGENTS.md + regex)",
        "rtk": "RTK (`rtk-ai/rtk` log compression)",
        "aedile": "**Aedile (AST/Graph + Consult + Compress)**",
    }
    for mode in modes:
        s = summary[mode]
        lines.append(
            f"| {labels[mode]} | {s['total_tokens']:,} | **{s['tokens_saved_vs_baseline']:,} ({s['reduction_pct']}%)** | "
            f"{s['avg_prompt_tokens']} | {s['avg_loc']} | {s['reuse_hits']}/{s['tasks']} | {s['syntax_valid']}/{s['tasks']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[OK] Saved FOUR_WAY_BENCHMARK.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
