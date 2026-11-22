# Supported Agents & Environments

Aedile runs locally over stdio JSON-RPC 2.0 (Model Context Protocol, **11 tools**) and supports `SessionStart` / `SubagentStart` lifecycle hooks.

---

## 1. One-Command Setup (Recommended)

Run inside your repository to register Aedile MCP and lifecycle hooks idempotently (creates `.aedile.bak` backups):

```bash
aedile setup
```

Preview planned changes without writing files, and verify your environment:

```bash
aedile setup --dry-run
aedile doctor
```

---

## 2. Manual Configuration

### Claude Code
`aedile setup` writes `.mcp.json` and `.claude/settings.local.json` with `SessionStart` (`aedile map`) and `SubagentStart` (`aedile map --budget 1200`) hooks. For global user settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "aedile": {
      "command": "python",
      "args": ["-m", "aedile"]
    }
  }
}
```

### Cursor
`aedile setup` writes `.cursor/mcp.json`. You can also compile `.cursorrules` with:

```bash
aedile compile-rules
```

### Windsurf / Copilot / Gemini CLI / Codex / Other MCP Hosts
Point any MCP-compatible host to:

```bash
python -m aedile
```

All JSON-RPC traffic uses `stdin`/`stdout`; diagnostics go to `stderr`.
