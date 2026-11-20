import json
import os
import sys
import traceback
from typing import Any

from aedile import __version__
from aedile.core.debt import format_debt_ledger, scan_debt
from aedile.core.graph import ArchitectureGraph
from aedile.core.inference import infer_layers
from aedile.core.mapper import build_codebase_map
from aedile.core.models import SourceFile
from aedile.core.optimizer import ReasoningOptimizer
from aedile.core.reviewer import format_review, review_changes
from aedile.core.scanner import Scanner
from aedile.core.similarity import SimilarityEngine
from aedile.core.verifier import ArchitectureVerifier
from aedile.infrastructure.cache import ScanCache
from aedile.infrastructure.telemetry import TelemetryStore
from aedile.infrastructure.watcher import WorkspaceWatcher
from aedile.shared.config import Config

sys.stderr.write("[Aedile Server] Stdio MCP Server initializing...\n")


class AedileMcpServer:
    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = os.path.abspath(project_root or os.getcwd())

        config_path = os.path.join(self.project_root, "aedile.toml")
        if os.path.exists(config_path):
            try:
                self.config = Config.load_from_file(config_path)
            except Exception as e:
                sys.stderr.write(f"[Aedile Server] Config parse error, fallback: {e}\n")
                self.config = Config()
        else:
            self.config = Config()
            for d in ["src", "lib", "app", "."]:
                if os.path.isdir(os.path.join(self.project_root, d)) and d != ".":
                    self.config.src_dirs = [d]
                    break

        cache_file = os.path.join(self.project_root, ".aedile", "cache.json")
        self.cache = ScanCache(cache_file)
        self.scanner = Scanner(self.config, self.cache)
        self.similarity_engine = SimilarityEngine(self.config)
        self.optimizer = ReasoningOptimizer(self.config)
        self.verifier = ArchitectureVerifier(self.config)
        self.telemetry = TelemetryStore(self.project_root)
        self.watcher = WorkspaceWatcher()

        self.files: list[SourceFile] = []
        self.graph: ArchitectureGraph | None = None
        self.refresh_index(force=True)

    def refresh_index(self, force: bool = False) -> None:
        """Triggers a cached scan when files have changed on disk."""
        try:
            if not force and self.files:
                tracked = [sf.filepath for sf in self.files if os.path.exists(sf.filepath)]
                if len(tracked) == len(self.files) and not self.watcher.has_changes(tracked):
                    return
            self.files, self.graph = self.scanner.scan_project(self.project_root)
            if not self.config.layer_order:
                infer_layers(self.files, self.config)
            self.similarity_engine.index_project(self.files)
            self.watcher.diff([sf.filepath for sf in self.files])
        except Exception as e:
            sys.stderr.write(f"[Aedile Server] Codebase scan error: {e}\n")

    def handle_consult(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Single-turn plan review: reuse, stdlib, deps, and pre-edit verification."""
        self.refresh_index()
        plan = arguments.get("proposed_plan", "")
        proposed_changes = arguments.get("proposed_changes", [])

        output = ["### Aedile Engineering Guidance Review"]
        reused_count = 0
        prevented_count = 0

        if plan:
            similar = self.similarity_engine.search_symbols(plan)
            stdlib = self.similarity_engine.check_stdlib(plan)
            deps = self.similarity_engine.check_dependencies(plan, self.project_root)
            reused_count = len(similar) + len(deps)

            if similar:
                output.append("\n#### Codebase Reuse Opportunities [Inferred: BM25/AST]")
                output.append("Reuse existing abstractions instead of duplicating:")
                for s in similar:
                    sig = s.get("signature") or ""
                    output.append(
                        f"- **{s['name']}{sig}** ({s['kind']}) in {s['relative_path']}:L{s['line']} (Score: {s['score']})"
                    )

            if stdlib:
                output.append("\n#### Python Standard Library [Inferred]")
                for s in stdlib:
                    output.append(f"- **{s['module']}**: {s['description']}")

            if deps:
                output.append("\n#### Declared Dependencies [Observed: pyproject.toml/requirements]")
                for d in deps:
                    output.append(f"- Reusable package **{d}** is already declared.")

            opt_plan = self.optimizer.optimize_plan(plan, similar, stdlib, deps)
            opt_plan_cleaned = opt_plan.replace(
                "### 🛡️ AEDILE ENGINEERING INTELLIGENCE REVIEW\n", ""
            ).strip()
            output.append("\n" + opt_plan_cleaned)

        if proposed_changes:
            violations = self.verifier.verify_changes(
                self.project_root, self.files, proposed_changes
            )
            prevented_count = len(violations)
            if violations:
                output.append("\n#### Architectural Violations Detected [Observed: AST/Graph]")
                for v in violations:
                    severity = "ERROR" if v.severity == "error" else "WARNING"
                    output.append(
                        f"- **{severity}** in {v.relative_path}:L{v.line} ({v.rule_name}): {v.message}"
                    )
            else:
                output.append("\n#### Architecture Compliant [Observed: AST/Graph]")
                output.append("Proposed file changes comply with layering and cycle rules.")

        est_saved = reused_count * 350 + prevented_count * 500
        self.telemetry.record(
            "aedile_consult",
            reused_symbols=reused_count,
            violations_prevented=prevented_count,
            estimated_tokens_saved=est_saved,
        )
        return {"content": [{"type": "text", "text": "\n".join(output)}]}

    def handle_verify_architecture(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.refresh_index()
        proposed_changes = arguments.get("proposed_changes", [])
        violations = self.verifier.verify_changes(self.project_root, self.files, proposed_changes)
        self.telemetry.record("aedile_verify_architecture", violations_prevented=len(violations))
        if not violations:
            return {"content": [{"type": "text", "text": "Architecture compliant (0 violations)."}]}
        lines = [f"Found {len(violations)} architectural violation(s):"]
        for v in violations:
            lines.append(f"- [{v.severity.upper()}] {v.relative_path}:L{v.line} ({v.rule_name}): {v.message}")
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    def handle_graph(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.refresh_index()
        graph = self.graph or ArchitectureGraph()
        fmt = arguments.get("format", "mermaid")
        module = arguments.get("module")
        if module:
            blast = sorted(graph.get_blast_radius(module))
            metrics = graph.get_coupling_metrics(module)
            text = (
                f"Module `{module}` | fan_in={metrics['fan_in']} fan_out={metrics['fan_out']} "
                f"instability={metrics['instability']}\n"
                f"Transitive dependents ({len(blast)}): {', '.join(blast) if blast else 'none'}"
            )
            return {"content": [{"type": "text", "text": text}]}
        out = graph.export_svg() if fmt == "svg" else graph.export_mermaid()
        return {"content": [{"type": "text", "text": out}]}

    def handle_map(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.refresh_index()
        budget = int(arguments.get("budget", 2000))
        text = build_codebase_map(self.files, self.config, budget_chars=budget)
        return {"content": [{"type": "text", "text": text or "No public symbols indexed."}]}

    def handle_review(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.refresh_index()
        graph = self.graph or ArchitectureGraph()
        violations = self.scanner.run_rules(self.files, graph, self.project_root)
        changed = arguments.get("changed_paths")
        findings = review_changes(
            self.project_root, self.files, graph, violations, self.config, changed_paths=changed
        )
        return {"content": [{"type": "text", "text": format_review(findings)}]}

    def handle_debt(self, arguments: dict[str, Any]) -> dict[str, Any]:
        marker = arguments.get("marker")
        entries = scan_debt(self.project_root, self.config, custom_marker=marker)
        return {"content": [{"type": "text", "text": format_debt_ledger(entries)}]}

    def _tool_catalog(self) -> list[dict[str, Any]]:
        """Compact tool schemas minimizing agent context overhead."""
        return [
            {
                "name": "aedile_consult",
                "description": "Consult before coding: reuse matches, stdlib/dep hints, and pre-edit architecture verification.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "proposed_plan": {"type": "string"},
                        "proposed_changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "action": {"type": "string", "enum": ["add", "modify", "delete"]},
                                    "imports": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["path", "action"],
                            },
                        },
                    },
                    "required": ["proposed_plan"],
                },
            },
            {
                "name": "aedile_verify_architecture",
                "description": "Simulate add/modify/delete changes against cycle, layer, boundary, and dangling-import rules.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "proposed_changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "action": {"type": "string", "enum": ["add", "modify", "delete"]},
                                    "imports": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["path", "action"],
                            },
                        }
                    },
                    "required": ["proposed_changes"],
                },
            },
            {
                "name": "aedile_map",
                "description": "Return token-budgeted AST codebase symbol map.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"budget": {"type": "integer"}},
                },
            },
            {
                "name": "aedile_graph",
                "description": "Export dependency graph (mermaid/svg) or query module blast radius.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "enum": ["mermaid", "svg"]},
                        "module": {"type": "string"},
                    },
                },
            },
            {
                "name": "aedile_review",
                "description": "Blast-radius & caller-aware architectural review of changed files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "changed_paths": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            {
                "name": "aedile_debt",
                "description": "List `# shortcut:` / `# aedile-waive:` architectural debt ledger.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"marker": {"type": "string"}},
                },
            },
        ]

    def run(self) -> None:
        """Stdio loop reading JSON-RPC messages."""
        sys.stderr.write("[Aedile Server] Stdio listener active.\n")
        handlers = {
            "aedile_consult": self.handle_consult,
            "aedile_verify_architecture": self.handle_verify_architecture,
            "aedile_graph": self.handle_graph,
            "aedile_map": self.handle_map,
            "aedile_review": self.handle_review,
            "aedile_debt": self.handle_debt,
        }
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line)
                method = request.get("method")
                req_id = request.get("id")

                if method == "initialize":
                    self._send(
                        {
                            "jsonrpc": "2.0",
                            "result": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {"tools": {}},
                                "serverInfo": {"name": "aedile", "version": __version__},
                            },
                            "id": req_id,
                        }
                    )
                elif method == "notifications/initialized":
                    continue
                elif method == "tools/list":
                    self._send(
                        {"jsonrpc": "2.0", "result": {"tools": self._tool_catalog()}, "id": req_id}
                    )
                elif method == "tools/call":
                    params = request.get("params", {})
                    name = params.get("name")
                    arguments = params.get("arguments", {})
                    try:
                        handler = handlers.get(name)
                        if handler is not None:
                            result = handler(arguments)
                        else:
                            result = {
                                "content": [
                                    {"type": "text", "text": f"Error: Tool '{name}' not found."}
                                ],
                                "isError": True,
                            }
                    except Exception as e:
                        result = {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Execution error in '{name}': {e}\n{traceback.format_exc()}",
                                }
                            ],
                            "isError": True,
                        }
                    self._send({"jsonrpc": "2.0", "result": result, "id": req_id})

            except Exception as e:
                sys.stderr.write(f"[Aedile Server] Parsing Error: {e}\n")

    def _send(self, response: dict[str, Any]) -> None:
        try:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"[Aedile Server] Write Error: {e}\n")


if __name__ == "__main__":
    server = AedileMcpServer()
    server.run()
