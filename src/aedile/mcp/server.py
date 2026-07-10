import json
import os
import sys
import traceback
from typing import Any

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile
from aedile.core.optimizer import ReasoningOptimizer
from aedile.core.scanner import Scanner
from aedile.core.similarity import SimilarityEngine
from aedile.core.verifier import ArchitectureVerifier
from aedile.infrastructure.cache import ScanCache
from aedile.shared.config import Config

# Force stderr streaming for console debugging
sys.stdout = sys.stdout
sys.stderr.write("[Aedile Server] Redesigned Stdio MCP Server initializing...\n")


class AedileMcpServer:
    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = os.path.abspath(project_root or os.getcwd())

        # Load config or fall back to default
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

        self.cache = ScanCache(self.project_root)
        self.scanner = Scanner(self.config, self.cache)
        self.similarity_engine = SimilarityEngine(self.config)
        self.optimizer = ReasoningOptimizer(self.config)
        self.verifier = ArchitectureVerifier(self.config)

        self.files: list[SourceFile] = []
        self.graph: ArchitectureGraph | None = None
        self.refresh_index()

    def refresh_index(self) -> None:
        """Triggers a cached scan of the repository structure."""
        try:
            self.files, self.graph = self.scanner.scan_project(self.project_root)
            self.similarity_engine.index_project(self.files)
        except Exception as e:
            sys.stderr.write(f"[Aedile Server] Codebase scan error: {e}\n")

    def handle_consult(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Provides a single-turn consolidated engineering plan review: codebase reuse,

        standard library suggestions, dependency checks, and simulated import integrity verifications.
        """
        self.refresh_index()
        plan = arguments.get("proposed_plan", "")
        proposed_changes = arguments.get("proposed_changes", [])

        output = ["### 🛡️ Aedile Engineering Guidance Review"]

        if plan:
            # Match similarities, stdlib, and pre-installed dependencies
            similar = self.similarity_engine.search_symbols(plan)
            stdlib = self.similarity_engine.check_stdlib(plan)
            deps = self.similarity_engine.check_dependencies(plan, self.project_root)

            if similar:
                output.append("\n#### 🔍 Codebase Reuse Opportunities")
                output.append("Do NOT duplicate logic. Reuse these existing abstractions:")
                for s in similar:
                    output.append(
                        f"- **{s['name']}** ({s['kind']}) in {s['relative_path']}:L{s['line']} (Confidence: {s['score']})"
                    )

            if stdlib:
                output.append("\n#### 📦 Python Standard Library")
                for s in stdlib:
                    output.append(f"- **{s['module']}**: {s['description']}")

            if deps:
                output.append("\n#### 🔌 Declared Dependencies")
                for d in deps:
                    output.append(f"- Reusable package **{d}** is already pre-installed.")

            # General reasoning advice
            opt_plan = self.optimizer.optimize_plan(plan, similar, stdlib, deps)
            # Crop title from optimizer output to prevent duplicate header
            opt_plan_cleaned = opt_plan.replace(
                "### 🛡️ AEDILE ENGINEERING INTELLIGENCE REVIEW\n", ""
            ).strip()
            output.append("\n" + opt_plan_cleaned)

        if proposed_changes:
            # Simulates imports and runs layering/cycle checks
            violations = self.verifier.verify_changes(
                self.project_root, self.files, proposed_changes
            )
            if violations:
                output.append("\n#### ⚠️ Architectural Violations Detected")
                for v in violations:
                    severity = "ERROR" if v.severity == "error" else "WARNING"
                    output.append(
                        f"- **{severity}** in {v.relative_path}:L{v.line} ({v.rule_name}): {v.message}"
                    )
            else:
                output.append("\n#### ✅ Architecture Compliant")
                output.append("Proposed file changes comply with layering and cycle rules.")

        return {"content": [{"type": "text", "text": "\n".join(output)}]}

    def run(self) -> None:
        """Stdio loop reading JSON-RPC messages."""
        sys.stderr.write("[Aedile Server] Stdio listener active.\n")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line)
                method = request.get("method")
                req_id = request.get("id")

                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "aedile", "version": "1.0.0"},
                        },
                        "id": req_id,
                    }
                    self._send(response)

                elif method == "notifications/initialized":
                    continue

                elif method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "result": {
                            "tools": [
                                {
                                    "name": "aedile_consult",
                                    "description": "Consult Aedile before implementing. Returns codebase symbol matches, stdlib alternatives, dependency reuse options, and checks proposed imports for cycles or layering violations.",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "proposed_plan": {
                                                "type": "string",
                                                "description": "General description of the feature logic you want to implement.",
                                            },
                                            "proposed_changes": {
                                                "type": "array",
                                                "description": "Optional list of files and imports you plan to add or modify.",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "path": {
                                                            "type": "string",
                                                            "description": "Relative file path of the modified/added file.",
                                                        },
                                                        "action": {
                                                            "type": "string",
                                                            "enum": ["add", "modify"],
                                                            "description": "Change action.",
                                                        },
                                                        "imports": {
                                                            "type": "array",
                                                            "items": {"type": "string"},
                                                            "description": "Imports planned in this module.",
                                                        },
                                                    },
                                                    "required": ["path", "action"],
                                                },
                                            },
                                        },
                                        "required": ["proposed_plan"],
                                    },
                                }
                            ]
                        },
                        "id": req_id,
                    }
                    self._send(response)

                elif method == "tools/call":
                    params = request.get("params", {})
                    name = params.get("name")
                    arguments = params.get("arguments", {})

                    result = None
                    try:
                        if name == "aedile_consult":
                            result = self.handle_consult(arguments)
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

                    response = {"jsonrpc": "2.0", "result": result, "id": req_id}
                    self._send(response)

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
