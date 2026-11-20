import html
import json
import os
import time
from typing import Any


class TelemetryStore:
    """Local-only session telemetry stored in `.aedile/telemetry.jsonl`."""

    def __init__(self, project_root: str) -> None:
        self.project_root = os.path.abspath(project_root)
        self.log_path = os.path.join(self.project_root, ".aedile", "telemetry.jsonl")

    def record(
        self,
        event: str,
        reused_symbols: int = 0,
        violations_prevented: int = 0,
        estimated_tokens_saved: int = 0,
    ) -> None:
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event": event,
                "reused_symbols": reused_symbols,
                "violations_prevented": violations_prevented,
                "estimated_tokens_saved": estimated_tokens_saved,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def summary(self) -> dict[str, Any]:
        events = 0
        reused = 0
        prevented = 0
        tokens_saved = 0
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        events += 1
                        reused += int(data.get("reused_symbols", 0))
                        prevented += int(data.get("violations_prevented", 0))
                        tokens_saved += int(data.get("estimated_tokens_saved", 0))
            except Exception:
                pass
        return {
            "consultations": events,
            "reused_symbols": reused,
            "violations_prevented": prevented,
            "estimated_tokens_saved": tokens_saved,
        }

    def statusline(self) -> str:
        s = self.summary()
        return (
            f"Aedile | consults: {s['consultations']} | "
            f"reused: {s['reused_symbols']} | "
            f"prevented: {s['violations_prevented']} | "
            f"~{s['estimated_tokens_saved']} tokens saved"
        )

    def render_board_html(self) -> str:
        s = self.summary()
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Aedile Local Telemetry Board</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 28px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-top: 20px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  .val {{ font-size: 2rem; font-weight: 700; color: #58a6ff; }}
</style>
</head>
<body>
  <h1>Aedile Local Telemetry Board</h1>
  <p>Project: <code>{html.escape(self.project_root)}</code> (100% local, zero external telemetry)</p>
  <div class="grid">
    <div class="card"><div>Consultations</div><div class="val">{s["consultations"]}</div></div>
    <div class="card"><div>Symbols Reused</div><div class="val">{s["reused_symbols"]}</div></div>
    <div class="card"><div>Violations Prevented</div><div class="val">{s["violations_prevented"]}</div></div>
    <div class="card"><div>Est. Tokens Saved</div><div class="val">{s["estimated_tokens_saved"]}</div></div>
  </div>
</body>
</html>"""
