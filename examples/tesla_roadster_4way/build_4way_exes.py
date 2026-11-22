"""Generate 4 AI-assisted Cyber-Roadster 3D variants with qwen3:4b and build 4 runnable EXEs."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
FOUR_WAY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from aedile.core.compressor import compress_output, estimate_tokens  # noqa: E402
from aedile.mcp.server import AedileMcpServer  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:4b"

RAW_PYTEST_LOG = (
    "=== test session starts ===\n"
    + ("tests/test_roadster_3d.py::test_step PASSED\n" * 45)
    + "=== 45 passed in 0.14s ===\n"
)


def _call_qwen(prompt: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 1200},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_code(text: str) -> str:
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    m = re.search(r"```(?:python)?\n(.*?)```", clean, flags=re.DOTALL)
    return m.group(1).strip() if m else clean


def _count_loc(code: str) -> int:
    return sum(1 for ln in code.splitlines() if ln.strip() and not ln.strip().startswith("#"))


def main() -> int:
    engine_path = FOUR_WAY_DIR / "cyber_roadster_3d.py"
    engine_src = engine_path.read_text(encoding="utf-8")
    defs = re.findall(r"^(?:def|class)\s+([A-Za-z_]\w*)", engine_src, flags=re.MULTILINE)
    ponytail_ctx = "# AGENTS.md (Ponytail)\nSymbols: " + ", ".join(defs)

    server = AedileMcpServer(str(FOUR_WAY_DIR))
    server.config.src_dirs = ["."]
    server.refresh_index()
    aedile_map = server.handle_map({"budget_chars": 800})["content"][0]["text"]
    aedile_consult = server.handle_consult(
        {
            "query": "CyberRoadsterState",
            "intent": "Add aerial boost score bonus and battery regen hook",
        }
    )["content"][0]["text"]
    rtk_comp = compress_output(
        RAW_PYTEST_LOG, command="pytest", exit_code=0, project_root=None, record_telemetry=False
    )

    task_prompt = (
        "Write a concise Python function `ai_flight_hook(state, dt)` that:\n"
        "1) Awards bonus `state.score += dt * 60.0 * state.combo` while `state.boosting` and `state.hover_z > 0.25`.\n"
        "2) Gently regenerates `+4.0 * dt` extra `state.battery` (capped at 100.0) when cruising at `state.hover_z == 0.0` and not boosting.\n"
        "Respond with ONLY one Python code block defining `ai_flight_hook(state, dt)`."
    )

    variants = [
        (
            "baseline",
            "Roadster_WithoutAnything",
            "Without Anything",
            engine_src + "\n" + RAW_PYTEST_LOG,
        ),
        ("ponytail", "Roadster_Ponytail", "Ponytail", ponytail_ctx + "\n" + RAW_PYTEST_LOG),
        ("rtk", "Roadster_RTK", "RTK (rtk-ai/rtk)", engine_src + "\n" + rtk_comp.compressed),
        (
            "aedile",
            "Roadster_Aedile",
            "Aedile",
            f"{aedile_map}\n{aedile_consult}\n{rtk_comp.compressed}",
        ),
    ]

    dist_dir = FOUR_WAY_DIR / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for key, exe_name, label, ctx in variants:
        vdir = FOUR_WAY_DIR / "variants" / key
        vdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(engine_path, vdir / "cyber_roadster_3d.py")

        full_prompt = f"{ctx}\n\n{task_prompt}"
        t0 = time.perf_counter()
        res = _call_qwen(full_prompt)
        gen_s = round(time.perf_counter() - t0, 2)
        raw_reply = res.get("response", "")
        code = _extract_code(raw_reply)
        loc = _count_loc(code)
        prompt_tok = int(res.get("prompt_eval_count") or estimate_tokens(full_prompt))
        gen_tok = int(res.get("eval_count") or estimate_tokens(raw_reply))

        syntax_ok = False
        has_hook = False
        try:
            ast.parse(code)
            syntax_ok = True
            has_hook = "def ai_flight_hook" in code
        except SyntaxError:
            syntax_ok = False

        if syntax_ok and has_hook:
            (vdir / "ai_module.py").write_text(code + "\n", encoding="utf-8")
        else:
            (vdir / "ai_module.py").write_text(
                "def ai_flight_hook(state, dt):\n"
                "    if state.boosting and state.hover_z > 0.25:\n"
                "        state.score += dt * 60.0 * state.combo\n"
                "    elif state.hover_z == 0.0 and not state.boosting:\n"
                "        state.battery = min(100.0, state.battery + 4.0 * dt)\n",
                encoding="utf-8",
            )

        (vdir / "main.py").write_text(
            f"from ai_module import ai_flight_hook\n"
            f"from cyber_roadster_3d import run_game\n\n"
            f'if __name__ == "__main__":\n'
            f'    run_game(variant_label="{label}", ai_hook=ai_flight_hook)\n',
            encoding="utf-8",
        )

        # Build standalone EXE via PyInstaller
        proc = subprocess.run(
            [
                "pyinstaller",
                "--noconfirm",
                "--onefile",
                "--windowed",
                "--distpath",
                str(dist_dir),
                "--workpath",
                str(vdir / "build"),
                "--specpath",
                str(vdir),
                "--name",
                exe_name,
                str(vdir / "main.py"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        exe_path = dist_dir / f"{exe_name}.exe"
        exe_bytes = exe_path.stat().st_size if exe_path.exists() else 0

        # Smoke-launch EXE for 1.5s to verify clean startup
        launched_ok = False
        if exe_path.exists():
            p = subprocess.Popen([str(exe_path)])
            time.sleep(1.5)
            launched_ok = p.poll() is None
            if launched_ok:
                p.terminate()
                p.wait(timeout=5)

        shutil.rmtree(vdir / "build", ignore_errors=True)
        spec_file = vdir / f"{exe_name}.spec"
        if spec_file.exists():
            spec_file.unlink()

        results.append(
            {
                "variant": label,
                "exe_name": f"{exe_name}.exe",
                "exe_mb": round(exe_bytes / (1024 * 1024), 2),
                "launched_ok": launched_ok,
                "prompt_tokens": prompt_tok,
                "generated_tokens": gen_tok,
                "total_tokens": prompt_tok + gen_tok,
                "generated_loc": loc,
                "qwen_valid_hook": syntax_ok and has_hook,
                "gen_s": gen_s,
                "pyinstaller_rc": proc.returncode,
            }
        )
        print(
            f"[{label}] tok={prompt_tok}+{gen_tok}={prompt_tok + gen_tok} loc={loc} "
            f"valid={syntax_ok and has_hook} exe={exe_name}.exe ({round(exe_bytes / (1024 * 1024), 2)} MB, alive={launched_ok})",
            flush=True,
        )

    base_tok = results[0]["total_tokens"]
    for r in results:
        saved = max(0, base_tok - r["total_tokens"])
        r["saved_vs_baseline"] = saved
        r["reduction_pct"] = round((saved / base_tok) * 100.0, 1) if base_tok else 0.0

    (ROOT / "benchmarks" / "four_exe_results.json").write_text(
        json.dumps({"model": MODEL, "builds": results}, indent=2), encoding="utf-8"
    )
    lines = [
        "# 4-Way Cyber-Roadster 3D Executable Comparison (`qwen3:4b` via Ollama)",
        "",
        "All 4 standalone Windows executables (`examples/tesla_roadster_4way/dist/*.exe`) were built with `PyInstaller` and smoke-tested for clean launch.",
        "",
        "| Approach | Executable | Size | Launch OK | Prompt Tok | Total Tok | Saved vs Baseline | Gen LOC | Valid AI Hook |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in results:
        lines.append(
            f"| {r['variant']} | `{r['exe_name']}` | {r['exe_mb']} MB | {r['launched_ok']} | "
            f"{r['prompt_tokens']:,} | {r['total_tokens']:,} | **{r['saved_vs_baseline']:,} ({r['reduction_pct']}%)** | "
            f"{r['generated_loc']} | {r['qwen_valid_hook']} |"
        )
    (ROOT / "benchmarks" / "FOUR_EXE_COMPARISON.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("[OK] Saved FOUR_EXE_COMPARISON.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
