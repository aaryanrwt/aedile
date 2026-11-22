import html
import json
from typing import Any

from aedile import __version__
from aedile.core.graph import ArchitectureGraph
from aedile.core.models import Report


def to_json(report: Report) -> str:
    """Serializes a Report to formatted JSON."""
    payload: dict[str, Any] = {
        "project_name": report.project_name,
        "generated_at": report.generated_at,
        "scan_time_seconds": report.scan_time_seconds,
        "metrics": {
            "total_files": report.metrics.total_files,
            "total_loc": report.metrics.total_loc,
            "total_violations": report.metrics.total_violations,
            "risk_score": report.metrics.risk_score,
            "dependency_cycles": report.metrics.dependency_cycles,
            "layer_violations": report.metrics.layer_violations,
            "dead_symbols": report.metrics.dead_symbols,
            "duplicate_groups": report.metrics.duplicate_groups,
        },
        "violations": [v.to_dict() for v in report.violations],
    }
    return json.dumps(payload, indent=2)


def to_sarif(report: Report) -> str:
    """Exports architectural violations as SARIF 2.1.0 for GitHub Code Scanning."""
    rules_seen: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for v in report.violations:
        if v.rule_name not in rules_seen:
            rules_seen[v.rule_name] = {
                "id": v.rule_name,
                "name": v.rule_name,
                "shortDescription": {"text": f"Aedile architectural rule: {v.rule_name}"},
            }
        results.append(
            {
                "ruleId": v.rule_name,
                "level": "error" if v.severity == "error" else "warning",
                "message": {"text": v.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": v.relative_path},
                            "region": {"startLine": max(1, v.line)},
                        }
                    }
                ],
            }
        )

    sarif: dict[str, Any] = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Aedile",
                        "version": __version__,
                        "rules": list(rules_seen.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


def to_html(report: Report, graph: ArchitectureGraph) -> str:
    """Renders a self-contained HTML architecture dashboard with embedded SVG graph."""
    svg_graph = graph.export_svg()
    rows = []
    for v in report.violations:
        badge_cls = "err" if v.severity == "error" else "warn"
        rows.append(
            "<tr>"
            f"<td><span class='badge {badge_cls}'>{html.escape(v.severity.upper())}</span></td>"
            f"<td><code>{html.escape(v.rule_name)}</code></td>"
            f"<td><code>{html.escape(v.relative_path)}:{v.line}</code></td>"
            f"<td>{html.escape(v.message)}</td>"
            "</tr>"
        )
    table_body = (
        "\n".join(rows) if rows else "<tr><td colspan='4'>No violations detected.</td></tr>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Aedile Architecture Report — {html.escape(report.project_name)}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; }}
  .card .val {{ font-size: 1.6rem; font-weight: 700; color: #58a6ff; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; background: #161b22; }}
  th, td {{ padding: 10px 12px; border-bottom: 1px solid #30363d; text-align: left; font-size: 0.9rem; }}
  .badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
  .err {{ background: #da3633; color: #fff; }}
  .warn {{ background: #d29922; color: #0d1117; }}
  .graph-box {{ border: 1px solid #30363d; border-radius: 8px; overflow: hidden; margin: 20px 0; max-height: 520px; }}
</style>
</head>
<body>
  <h1>Aedile Architecture Report — {html.escape(report.project_name)}</h1>
  <p>Generated {html.escape(report.generated_at)} ({report.scan_time_seconds}s)</p>
  <div class="grid">
    <div class="card"><div>Files</div><div class="val">{report.metrics.total_files}</div></div>
    <div class="card"><div>Lines of Code</div><div class="val">{report.metrics.total_loc}</div></div>
    <div class="card"><div>Violations</div><div class="val">{report.metrics.total_violations}</div></div>
    <div class="card"><div>Risk Score</div><div class="val">{report.metrics.risk_score}</div></div>
  </div>
  <h2>Dependency Graph</h2>
  <div class="graph-box">{svg_graph}</div>
  <h2>Findings</h2>
  <table>
    <thead><tr><th>Severity</th><th>Rule</th><th>Location</th><th>Message</th></tr></thead>
    <tbody>{table_body}</tbody>
  </table>
</body>
</html>"""


def to_card_svg(report: Report) -> str:
    """Renders a shareable dark-theme SVG summary card for PRs and READMEs."""
    proj = html.escape(report.project_name)
    score = report.metrics.risk_score
    color = "#238636" if score < 15.0 else ("#d29922" if score < 40.0 else "#da3633")
    bar_w = max(8.0, min(260.0, (100.0 - score) * 2.6))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="200" viewBox="0 0 720 200" role="img" aria-label="Aedile Report Card: {proj}">
  <rect width="720" height="200" rx="14" fill="#0d1117"/>
  <rect x="0.5" y="0.5" width="719" height="199" rx="13.5" fill="none" stroke="#30363d"/>
  <text x="28" y="40" font-family="monospace" font-size="13" fill="#58a6ff">AEDILE v{html.escape(__version__)} ARCHITECTURE CARD</text>
  <text x="28" y="74" font-family="sans-serif" font-size="22" font-weight="700" fill="#e6edf3">{proj}</text>
  <text x="28" y="132" font-family="sans-serif" font-size="48" font-weight="800" fill="{color}">{score}<tspan dx="8" font-size="18" font-weight="600" fill="#8b949e">risk score</tspan></text>
  <text x="410" y="76" font-family="sans-serif" font-size="13" fill="#8b949e">Files: {report.metrics.total_files} | LOC: {report.metrics.total_loc}</text>
  <text x="410" y="102" font-family="sans-serif" font-size="13" fill="#8b949e">Violations: {report.metrics.total_violations} (Cycles: {report.metrics.dependency_cycles}, Layers: {report.metrics.layer_violations})</text>
  <rect x="410" y="122" width="260" height="14" rx="4" fill="#21262d"/>
  <rect x="410" y="122" width="{bar_w:.1f}" height="14" rx="4" fill="{color}"/>
  <text x="28" y="176" font-family="sans-serif" font-size="12" fill="#8b949e">Scan time: {report.scan_time_seconds}s | Generated: {html.escape(report.generated_at)}</text>
</svg>"""
