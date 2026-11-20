import json
import os
import shutil
import sys
from typing import Any

VALID_MODES = ("lite", "full", "ultra", "off")


def get_intensity_mode(project_root: str) -> str:
    """Returns active intensity mode from AEDILE_MODE env or `.aedile/mode`."""
    env_mode = os.environ.get("AEDILE_MODE", "").strip().lower()
    if env_mode in VALID_MODES:
        return env_mode
    mode_file = os.path.join(os.path.abspath(project_root), ".aedile", "mode")
    if os.path.exists(mode_file):
        try:
            with open(mode_file, encoding="utf-8") as f:
                val = f.read().strip().lower()
            if val in VALID_MODES:
                return val
        except OSError:
            pass
    return "full"


def set_intensity_mode(project_root: str, mode: str) -> str:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Choose from: {', '.join(VALID_MODES)}")
    aedile_dir = os.path.join(os.path.abspath(project_root), ".aedile")
    os.makedirs(aedile_dir, exist_ok=True)
    mode_file = os.path.join(aedile_dir, "mode")
    with open(mode_file, "w", encoding="utf-8") as f:
        f.write(mode + "\n")
    return mode_file


def _backup_file(path: str) -> None:
    if os.path.exists(path):
        shutil.copy2(path, path + ".aedile.bak")


def _merge_json_mcp(filepath: str, server_cmd: list[str], dry_run: bool) -> str:
    data: dict[str, Any] = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    mcp_servers = data.setdefault("mcpServers", {})
    mcp_servers["aedile"] = {"command": server_cmd[0], "args": server_cmd[1:]}
    if dry_run:
        return f"[dry-run] Would register Aedile MCP in {filepath}"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    _backup_file(filepath)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return f"[ok] Registered Aedile MCP in {filepath}"


def _write_claude_hooks(project_root: str, dry_run: bool) -> str:
    hooks_path = os.path.join(project_root, ".claude", "settings.local.json")
    data: dict[str, Any] = {}
    if os.path.exists(hooks_path):
        try:
            with open(hooks_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    hooks = data.setdefault("hooks", {})
    hooks["SessionStart"] = [
        {
            "matcher": "startup|resume|clear|compact",
            "hooks": [{"type": "command", "command": f"{sys.executable} -m aedile map"}],
        }
    ]
    hooks["SubagentStart"] = [
        {"hooks": [{"type": "command", "command": f"{sys.executable} -m aedile map --budget 1200"}]}
    ]
    if dry_run:
        return f"[dry-run] Would write SessionStart & SubagentStart hooks to {hooks_path}"
    os.makedirs(os.path.dirname(hooks_path), exist_ok=True)
    _backup_file(hooks_path)
    with open(hooks_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return f"[ok] Installed SessionStart & SubagentStart hooks in {hooks_path}"


def setup_agents(project_root: str, dry_run: bool = False) -> list[str]:
    """Idempotently configures Aedile MCP & lifecycle hooks for installed coding agents."""
    abs_root = os.path.abspath(project_root)
    py_exe = sys.executable
    results: list[str] = []

    # Project-local Cursor MCP & Claude Code hooks
    results.append(
        _merge_json_mcp(
            os.path.join(abs_root, ".cursor", "mcp.json"), [py_exe, "-m", "aedile"], dry_run
        )
    )
    results.append(
        _merge_json_mcp(os.path.join(abs_root, ".mcp.json"), [py_exe, "-m", "aedile"], dry_run)
    )
    results.append(_write_claude_hooks(abs_root, dry_run))

    # Windsurf / Copilot / Gemini instructions if directories exist
    gh_dir = os.path.join(abs_root, ".github")
    if os.path.isdir(gh_dir):
        copilot_path = os.path.join(gh_dir, "copilot-instructions.md")
        if dry_run:
            results.append(f"[dry-run] Would update {copilot_path}")
        else:
            _backup_file(copilot_path)
            with open(copilot_path, "w", encoding="utf-8") as f:
                f.write(
                    "# Aedile Architectural Guardrails\n\n"
                    "Consult `aedile_consult` via MCP before writing new modules or dependencies.\n"
                )
            results.append(f"[ok] Updated {copilot_path}")

    return results
