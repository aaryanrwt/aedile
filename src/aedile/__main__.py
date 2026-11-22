import argparse
import os
import sys
import time
from collections.abc import Sequence

from aedile import __version__
from aedile.cli.doctor import format_doctor, run_doctor
from aedile.cli.setup import VALID_MODES, get_intensity_mode, set_intensity_mode, setup_agents
from aedile.core.baseline import BaselineManager
from aedile.core.compressor import recall_output, run_and_compress
from aedile.core.debt import format_debt_ledger, scan_debt
from aedile.core.graph_insights import (
    detect_communities,
    explain_module,
    god_nodes,
    suggest_questions,
    surprising_connections,
)
from aedile.core.hotspots import profile_target
from aedile.core.inference import detect_src_dirs, infer_layers
from aedile.core.mapper import build_codebase_map
from aedile.core.reporter import to_card_svg, to_html, to_json, to_sarif
from aedile.core.reviewer import audit_repo, format_audit, format_review, review_changes
from aedile.core.scanner import Scanner
from aedile.infrastructure.cache import ScanCache
from aedile.infrastructure.telemetry import TelemetryStore
from aedile.mcp.server import AedileMcpServer
from aedile.shared.config import Config


def _load_config(project_root: str, infer: bool = True) -> Config:
    config_path = os.path.join(project_root, "aedile.toml")
    if os.path.exists(config_path):
        try:
            return Config.load_from_file(config_path)
        except Exception as e:
            sys.stderr.write(f"[Aedile] Config parse warning: {e}\n")
    cfg = Config()
    cfg.src_dirs = detect_src_dirs(project_root) if infer else cfg.src_dirs
    return cfg


def compile_agent_rules(project_root: str, mode: str | None = None) -> None:
    """Compiles Aedile's decision ladder and layer guidelines into agent rule files."""
    config = _load_config(project_root)
    active_mode = mode or get_intensity_mode(project_root)
    layers_str = (
        " -> ".join(config.layer_order)
        if config.layer_order
        else "None (No strict layers declared)"
    )
    src_dirs_str = ", ".join(config.src_dirs)

    rules_content = f"""# AEDILE ENGINEERING INTELLIGENCE LAYER GUIDELINES (Mode: {active_mode})
# Maintains architectural integrity & optimizes reasoning token efficiency.

You are pair programming with Aedile active ({active_mode} mode). Run all plans through Aedile's Decision Ladder BEFORE generating code:

## AEDILE DECISION LADDER

1. **Necessity**: Does this logic actually need to exist? If not, skip it.
2. **Reuse**: Does the codebase already contain this? Search first. NEVER duplicate code.
3. **Standard Library**: Can Python's standard library solve it? Prefer it.
4. **Existing Dependencies**: Can an existing declared dependency solve it? Check pyproject.toml.
5. **Existing Abstractions**: Reuse existing classes/functions instead of wrapping them.
6. **Architecture Layering**: Respect downward import flow rules.
7. **Dependency Cycles**: Circular module imports are strictly prohibited.
8. **Token Efficiency**: Accomplish the task with minimal diffs, files, and tool calls.

## REPOSITORY ARCHITECTURE

- **Project Name**: {config.project_name}
- **Source Folders**: {src_dirs_str}
- **Layer Flow Hierarchy (Downward Only)**: {layers_str}
- **Module Boundaries**: Symbols starting with private prefixes (e.g. '_') are private to their module.

## VERIFICATION

Before completing your task, invoke `aedile_consult` or `aedile_verify_architecture` via MCP.
"""

    for fname in (".cursorrules", ".claudeprompt"):
        out_path = os.path.join(project_root, fname)
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(rules_content)
        except Exception as e:
            sys.stderr.write(f"[Aedile] Error writing {fname}: {e}\n")
    sys.stderr.write("[Aedile] Successfully compiled rules to .cursorrules and .claudeprompt\n")


def _cmd_check(project_root: str, args: argparse.Namespace) -> int:
    start = time.time()
    cfg = _load_config(project_root)
    cache = ScanCache(os.path.join(project_root, ".aedile", "cache.json"))
    scanner = Scanner(cfg, cache)
    files, graph = scanner.scan_project(project_root)
    if args.infer_layers or not cfg.layer_order:
        infer_layers(files, cfg)
    violations = scanner.run_rules(files, graph, project_root)

    suppressed = 0
    baseline_mgr = BaselineManager(project_root)
    if args.update_baseline:
        path = baseline_mgr.save(violations)
        print(f"[Aedile] Saved baseline ({len(violations)} violations) to {path}")
        return 0
    if args.baseline:
        violations, suppressed = baseline_mgr.filter_new(violations)

    report = scanner.generate_report(files, graph, violations, time.time() - start)
    if args.format == "json":
        rendered = to_json(report)
    elif args.format == "sarif":
        rendered = to_sarif(report)
    elif args.format == "html":
        rendered = to_html(report, graph)
    elif args.format == "card":
        rendered = to_card_svg(report)
    else:
        lines = [
            f"Aedile v{__version__} | {report.metrics.total_files} files | "
            f"{report.metrics.total_loc} LOC | risk={report.metrics.risk_score} | "
            f"violations={len(violations)} (baselined={suppressed})"
        ]
        for v in violations:
            lines.append(
                f"  [{v.severity.upper()}] {v.relative_path}:L{v.line} ({v.rule_name}): {v.message}"
            )
        rendered = "\n".join(lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rendered)
        print(f"[Aedile] Report written to {args.output}")
    else:
        print(rendered)

    has_errors = any(v.severity == "error" for v in violations)
    return 1 if has_errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aedile",
        description="Aedile: Engineering Intelligence Layer & MCP Server for AI Coding Agents.",
    )
    parser.add_argument("--version", action="version", version=f"aedile {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # compile-rules
    p_rules = subparsers.add_parser("compile-rules", help="Compile .cursorrules and .claudeprompt.")
    p_rules.add_argument("--mode", choices=VALID_MODES, default=None)

    # check
    p_check = subparsers.add_parser("check", help="Run full-repository architectural checks.")
    p_check.add_argument(
        "--format", choices=("text", "json", "sarif", "html", "card"), default="text"
    )
    p_check.add_argument("--output", default=None)
    p_check.add_argument("--baseline", action="store_true")
    p_check.add_argument("--update-baseline", action="store_true")
    p_check.add_argument("--infer-layers", action="store_true")

    # graph
    p_graph = subparsers.add_parser(
        "graph", help="Export dependency graph (mermaid, svg, graphml, or cypher)."
    )
    p_graph.add_argument(
        "--format", choices=("mermaid", "svg", "graphml", "cypher"), default="mermaid"
    )
    p_graph.add_argument("--output", default=None)

    # map
    p_map = subparsers.add_parser("map", help="Emit token-budgeted AST codebase map.")
    p_map.add_argument("--budget", type=int, default=2000)

    # review
    p_review = subparsers.add_parser("review", help="Caller-aware blast-radius review.")
    p_review.add_argument("--base", default="HEAD")

    # debt
    p_debt = subparsers.add_parser("debt", help="List `# shortcut:` / `# aedile-waive:` ledger.")
    p_debt.add_argument("--marker", default=None)

    # setup
    p_setup = subparsers.add_parser("setup", help="Configure MCP & hooks for local AI agents.")
    p_setup.add_argument("--dry-run", action="store_true")

    # init
    subparsers.add_parser("init", help="Generate starter aedile.toml.")

    # mode
    p_mode = subparsers.add_parser("mode", help="Get or set intensity mode (lite|full|ultra|off).")
    p_mode.add_argument("value", nargs="?", choices=VALID_MODES)

    # board
    p_board = subparsers.add_parser(
        "board", help="Show local telemetry summary or export HTML board."
    )
    p_board.add_argument("--output", default=None)

    # explain
    p_explain = subparsers.add_parser(
        "explain", help="Explain a module's dependencies and blast radius."
    )
    p_explain.add_argument("module")

    # path
    p_path = subparsers.add_parser(
        "path", help="Find shortest dependency path between two modules."
    )
    p_path.add_argument("source")
    p_path.add_argument("target")

    # insights
    subparsers.add_parser(
        "insights", help="Show god nodes, communities, cross-subsystem bridges, and questions."
    )

    # audit
    subparsers.add_parser("audit", help="Run whole-repo ranked architectural audit.")

    # hotspots
    p_hot = subparsers.add_parser("hotspots", help="Profile a Python script and rank hotspots.")
    p_hot.add_argument("script")
    p_hot.add_argument("script_args", nargs="*")

    # doctor
    subparsers.add_parser("doctor", help="Check Python toolchain, cache, and agent integrations.")

    # compress / recall / gain (RTK-style token-cutting proxy)
    p_comp = subparsers.add_parser(
        "compress", help="Run a command and compress its output to save LLM tokens."
    )
    p_comp.add_argument("cmd", nargs=argparse.REMAINDER)

    p_recall = subparsers.add_parser(
        "recall", help="Retrieve full raw output saved from a compressed failure."
    )
    p_recall.add_argument("hash_prefix")

    subparsers.add_parser("gain", help="Show cumulative LLM token savings and reuse telemetry.")

    args = parser.parse_args(argv)
    project_root = os.getcwd()

    if args.command == "compile-rules":
        compile_agent_rules(project_root, mode=args.mode)
        return 0
    if args.command == "check":
        return _cmd_check(project_root, args)
    if args.command == "graph":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        _, graph = scanner.scan_project(project_root)
        if args.format == "svg":
            out = graph.export_svg()
        elif args.format == "graphml":
            out = graph.export_graphml()
        elif args.format == "cypher":
            out = graph.export_cypher()
        else:
            out = graph.export_mermaid()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out)
        else:
            print(out)
        return 0
    if args.command == "map":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        files, _ = scanner.scan_project(project_root)
        if not cfg.layer_order:
            infer_layers(files, cfg)
        print(build_codebase_map(files, cfg, budget_chars=args.budget))
        return 0
    if args.command == "review":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        files, graph = scanner.scan_project(project_root)
        violations = scanner.run_rules(files, graph, project_root)
        findings = review_changes(project_root, files, graph, violations, cfg, base_ref=args.base)
        print(format_review(findings))
        return 0
    if args.command == "debt":
        entries = scan_debt(project_root, _load_config(project_root), custom_marker=args.marker)
        print(format_debt_ledger(entries))
        return 0
    if args.command == "setup":
        for line in setup_agents(project_root, dry_run=args.dry_run):
            print(line)
        return 0
    if args.command == "init":
        src_dirs = detect_src_dirs(project_root)
        toml_path = os.path.join(project_root, "aedile.toml")
        if os.path.exists(toml_path):
            print(f"[Aedile] {toml_path} already exists.")
            return 0
        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(
                f'[project]\nname = "{os.path.basename(project_root)}"\n'
                f'src_dirs = {src_dirs!r}\nlanguages = ["python"]\n'
            )
        print(f"[Aedile] Created {toml_path}")
        return 0
    if args.command == "mode":
        if args.value:
            set_intensity_mode(project_root, args.value)
            print(f"Aedile mode set to: {args.value}")
        else:
            print(f"Current Aedile mode: {get_intensity_mode(project_root)}")
        return 0
    if args.command == "board":
        store = TelemetryStore(project_root)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(store.render_board_html())
            print(f"[Aedile] Telemetry board written to {args.output}")
        else:
            print(store.statusline())
        return 0
    if args.command == "explain":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        _, graph = scanner.scan_project(project_root)
        info = explain_module(graph, args.module)
        if not info["found"]:
            print(f"Module '{args.module}' not found. Candidates: {info['candidates']}")
            return 1
        print(
            f"Module: {info['module']}\n"
            f"Metrics: {info['metrics']}\n"
            f"Imports ({len(info['imports'])}): {', '.join(info['imports']) or 'none'}\n"
            f"Imported by ({len(info['imported_by'])}): {', '.join(info['imported_by']) or 'none'}\n"
            f"Blast radius ({len(info['blast_radius'])}): {', '.join(info['blast_radius']) or 'none'}"
        )
        return 0
    if args.command == "path":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        _, graph = scanner.scan_project(project_root)
        p = graph.find_shortest_path(args.source, args.target)
        print(" -> ".join(p) if p else f"No path from {args.source} to {args.target}.")
        return 0
    if args.command == "insights":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        _, graph = scanner.scan_project(project_root)
        comms = detect_communities(graph)
        print("God nodes:", god_nodes(graph, top_n=5))
        print(f"Communities: {len(comms)}")
        print(f"Cross-community bridges: {len(surprising_connections(graph, comms))}")
        for q in suggest_questions(graph, comms):
            print(f"- {q}")
        return 0
    if args.command == "audit":
        cfg = _load_config(project_root)
        scanner = Scanner(cfg, ScanCache(os.path.join(project_root, ".aedile", "cache.json")))
        files, graph = scanner.scan_project(project_root)
        violations = scanner.run_rules(files, graph, project_root)
        print(format_audit(audit_repo(project_root, files, graph, violations, cfg)))
        return 0
    if args.command == "hotspots":
        wall, spots = profile_target(args.script, project_root, args.script_args)
        print(f"Profiled {args.script} in {wall}s ({len(spots)} functions):")
        for h in spots[:10]:
            cov = f" [covered_by={h.covered_by}]" if h.covered_by else ""
            print(f"  {h.func_id}:L{h.line} share={h.share:.1%} score={h.score}{cov}")
        return 0
    if args.command == "doctor":
        print(format_doctor(run_doctor(project_root)))
        return 0
    if args.command == "compress":
        cmd = list(args.cmd)
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        if not cmd:
            sys.stderr.write("Usage: aedile compress <command> [args...]\n")
            return 2
        rc, res = run_and_compress(cmd, project_root=project_root)
        if res.compressed:
            print(res.compressed)
        sys.stderr.write(
            f"[aedile compress:{res.filter_used}] {res.raw_tokens}->{res.compressed_tokens} tok "
            f"(saved {res.tokens_saved}, {res.savings_pct}%)\n"
        )
        return rc
    if args.command == "recall":
        raw = recall_output(args.hash_prefix, project_root=project_root)
        if raw is None:
            sys.stderr.write(f"No recall log found for prefix '{args.hash_prefix}'.\n")
            return 1
        print(raw)
        return 0
    if args.command == "gain":
        summary = TelemetryStore(project_root).summary()
        print(
            f"Aedile Gain: {summary['estimated_tokens_saved']:,} tokens saved | "
            f"{summary['reused_symbols']} symbols reused | "
            f"{summary['violations_prevented']} violations prevented | "
            f"{summary['events']} tracked events"
        )
        return 0

    # Default: Start MCP Server
    sys.stderr.write("[Aedile] Launching Stdio MCP Server...\n")
    server = AedileMcpServer(project_root)
    try:
        server.run()
    except KeyboardInterrupt:
        sys.stderr.write("[Aedile] Server stopped by user.\n")
        return 0
    except Exception as e:
        sys.stderr.write(f"[Aedile] Server Error: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
