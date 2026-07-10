import argparse
import os
import sys
from typing import Sequence

from aedile.shared.config import Config
from aedile.mcp.server import AedileMcpServer


def compile_agent_rules(project_root: str) -> None:
    """Compiles Aedile's strict engineering thinking ladder and layer guidelines

    into .cursorrules and .claudeprompt system files.
    """
    config_path = os.path.join(project_root, "aedile.toml")
    config = Config()
    if os.path.exists(config_path):
        try:
            config = Config.load_from_file(config_path)
        except Exception:
            pass

    # Build the rules template
    layers_str = " -> ".join(config.layer_order) if config.layer_order else "None (No strict layers declared)"
    src_dirs_str = ", ".join(config.src_dirs)

    rules_content = f"""# AEDILE ENGINEERING INTELLIGENCE LAYER GUIDELINES
# Maintains architectural integrity & optimizes reasoning token efficiency.

You are pair programming with Aedile active. You MUST run all plans through Aedile's Engineering Ladder BEFORE generating code:

---

## 📐 AEDILE DECISION LADDER

1. **Necessity**: Does this feature/logic actually need to exist? If not, delete it.
2. **Reuse**: Does the codebase already contain this? Search first. **NEVER duplicate code.**
3. **Standard Library**: Can the standard library (e.g. pathlib, re, json, datetime) solve it? Prefer it.
4. **Existing Dependencies**: Can an existing project dependency solve it? Check pyproject.toml/requirements.txt.
5. **Existing Abstractions**: Reuse existing project classes/functions instead of writing new wrappers.
6. **Architecture Layering**: Respect our declared downward import flow rules.
7. **Dependency Cycles**: Circular module imports are strictly prohibited.
8. **Token Efficiency**: Plan to accomplish the task with minimal reasoning steps, files, and lines of code.

---

## 🏛️ REPOSITORY ARCHITECTURE SCHEMATICS

- **Project Name**: {config.project_name}
- **Source Folders**: {src_dirs_str}
- **Layer Flow Hierarchy (Downward Only)**: {layers_str}
- **Module Boundaries**: Symbols starting with private prefixes (e.g., '_') are private to their module.

---

## 🛠️ VERIFICATION

Before completing your implementation task, you MUST invoke the `aedile_verify_architecture` tool on your proposed file and import list to ensure you have not introduced dependency cycles or layer violations.
"""

    cursorrules_path = os.path.join(project_root, ".cursorrules")
    claudeprompt_path = os.path.join(project_root, ".claudeprompt")

    try:
        with open(cursorrules_path, "w", encoding="utf-8") as f:
            f.write(rules_content)
        with open(claudeprompt_path, "w", encoding="utf-8") as f:
            f.write(rules_content)
        sys.stderr.write(f"[Aedile] Successfully compiled rules to .cursorrules and .claudeprompt\n")
    except Exception as e:
        sys.stderr.write(f"[Aedile] Error compiling rules: {e}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aedile",
        description="Aedile: Engineering Intelligence Layer & MCP Server for AI Coding Agents.",
    )
    subparsers = parser.add_subparsers(dest="command")
    
    # compile-rules subcommand
    subparsers.add_parser(
        "compile-rules", 
        help="Compile Aedile's thinking ladder and project layers into .cursorrules / .claudeprompt templates."
    )

    args = parser.parse_args(argv)

    project_root = os.getcwd()

    if args.command == "compile-rules":
        compile_agent_rules(project_root)
        return 0
    else:
        # Default behavior: Start MCP Server
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
