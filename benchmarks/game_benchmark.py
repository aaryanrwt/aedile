"""Real Ollama Game Generation & Verification Benchmark: Ponytail vs. Aedile.

Generates two complete HTML5 Canvas games (Snake & Apple, Dino Runner) with `qwen3:4b`
using Ponytail and Aedile respectively, validates HTML + JS syntax (`node --check`),
audits game mechanics/visuals, and writes real measured results.
"""

import argparse
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from aedile.mcp.server import AedileMcpServer  # noqa: E402

SCRATCH_ROOT = os.path.join(tempfile.gettempdir(), "aedile_game_benchmark")

SNAKE_PROMPT = (
    "Build a complete, working, single-file HTML5 Canvas Snake & Apple game. "
    "Implement ALL JavaScript logic directly inside <script> (no placeholders or TODOs). "
    "Include: dark neon theme, grid board, smooth snake segments, glowing apple, "
    "Arrow/WASD controls, wall and self collision, live score & high score, "
    "and Game Over overlay with Space/Enter restart. Output ONLY one <!DOCTYPE html> block."
)

DINO_PROMPT = (
    "Build a complete, working, single-file HTML5 Canvas Dino Runner endless game. "
    "Implement ALL JavaScript logic directly inside <script> (no placeholders or TODOs). "
    "Include: scrolling ground, jumping & ducking dino, approaching cactus/bird obstacles, "
    "gravity & jump physics, collision detection, live score & speed scaling, "
    "and Game Over overlay with Space restart. Output ONLY one <!DOCTYPE html> block."
)


class _ScriptExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_script = False
        self.has_canvas = False
        self.scripts: list[str] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "canvas":
            self.has_canvas = True
        elif tag.lower() == "script":
            self.in_script = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.in_script:
            self.in_script = False
            self.scripts.append("".join(self._buf))

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self._buf.append(data)


def _extract_html(raw: str) -> str:
    matches = re.findall(r"(<!DOCTYPE.*?</html>|<html.*?</html>)", raw, re.DOTALL | re.IGNORECASE)
    if matches:
        return max(matches, key=len).strip()
    return raw.strip()


def _verify_game_html(html_text: str, kind: str) -> dict[str, Any]:
    parser = _ScriptExtractor()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    js_code = "\n".join(parser.scripts).strip()
    js_syntax_ok = False
    js_err = ""
    if js_code:
        with tempfile.NamedTemporaryFile(
            suffix=".js", mode="w", encoding="utf-8", delete=False
        ) as tf:
            tf.write(js_code)
            tf_path = tf.name
        try:
            proc = subprocess.run(
                ["node", "--check", tf_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            js_syntax_ok = proc.returncode == 0
            if not js_syntax_ok:
                js_err = (proc.stderr or proc.stdout).strip()[:200]
        except Exception as e:
            js_err = str(e)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    low = html_text.lower()
    has_loop = any(k in html_text for k in ("requestAnimationFrame", "setInterval"))
    has_controls = "keydown" in low or "addeventlistener" in low
    has_collision = any(k in low for k in ("collision", "gameover", "game_over", "isgameover"))
    has_score = "score" in low
    has_restart = any(k in low for k in ("restart", "reset", "init(", "startgame"))
    has_visuals = any(k in low for k in ("shadowblur", "gradient", "fillstyle", "arc("))

    checks = [
        parser.has_canvas,
        bool(js_code),
        js_syntax_ok,
        has_loop,
        has_controls,
        has_collision,
        has_score,
        has_restart,
        has_visuals,
    ]
    return {
        "loc": len(html_text.splitlines()),
        "bytes": len(html_text.encode("utf-8")),
        "has_canvas": parser.has_canvas,
        "js_syntax_ok": js_syntax_ok,
        "js_error": js_err,
        "has_loop": has_loop,
        "has_controls": has_controls,
        "has_collision": has_collision,
        "has_score": has_score,
        "has_restart": has_restart,
        "has_visuals": has_visuals,
        "checks_passed": sum(1 for c in checks if c),
        "checks_total": len(checks),
        "playable": parser.has_canvas
        and js_syntax_ok
        and has_loop
        and has_controls
        and has_collision,
    }


def _ollama_generate(model: str, system: str, prompt: str) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.0, "num_predict": 2200},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=400) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        "response": data.get("response", ""),
        "prompt_tokens": int(data.get("prompt_eval_count", 0)),
        "output_tokens": int(data.get("eval_count", 0)),
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--ponytail-dir", default=os.path.join(tempfile.gettempdir(), "ponytail"))
    args = parser.parse_args()

    ponytail_agents = os.path.join(args.ponytail_dir, "AGENTS.md")
    with open(ponytail_agents, encoding="utf-8") as f:
        ponytail_sys = f.read()

    srv = AedileMcpServer(REPO_ROOT)
    aedile_map = srv.handle_map({"budget": 1000})["content"][0]["text"]

    games = [("snake", SNAKE_PROMPT), ("dino", DINO_PROMPT)]
    results: dict[str, Any] = {"model": args.model, "games": {}}

    for gname, gprompt in games:
        consult = srv.handle_consult({"proposed_plan": gprompt, "proposed_changes": []})["content"][
            0
        ]["text"]
        aedile_sys = f"{aedile_map}\n\n{consult}"

        results["games"][gname] = {}
        for tool_name, sys_prompt in (("ponytail", ponytail_sys), ("aedile", aedile_sys)):
            print(f"Generating {gname} via {tool_name} ({args.model})...", flush=True)
            gen = _ollama_generate(args.model, sys_prompt, gprompt)
            html_code = _extract_html(gen["response"])
            out_path = os.path.join(SCRATCH_ROOT, "games", tool_name, f"{gname}.html")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html_code)
            audit = _verify_game_html(html_code, gname)
            results["games"][gname][tool_name] = {
                "file": out_path,
                "prompt_tokens": gen["prompt_tokens"],
                "output_tokens": gen["output_tokens"],
                "elapsed_s": gen["elapsed_s"],
                "audit": audit,
            }
            print(
                f"  -> {tool_name}/{gname}.html: playable={audit['playable']}, "
                f"js_ok={audit['js_syntax_ok']}, checks={audit['checks_passed']}/{audit['checks_total']}, "
                f"loc={audit['loc']}, out_tok={gen['output_tokens']}, time={gen['elapsed_s']}s",
                flush=True,
            )

    out_json = os.path.join(REPO_ROOT, "benchmarks", "game_benchmark_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"[OK] Saved {out_json}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
