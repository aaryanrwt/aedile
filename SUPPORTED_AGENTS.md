# Supported Agents & Environments

Aedile is designed to be agent-agnostic. It communicates using standard input/output (stdio) JSON-RPC 2.0 frames over the Model Context Protocol (MCP). Any assistant or editor supporting MCP can integrate with Aedile.

---

## 1. Claude Code

Aedile runs directly inside Claude Code's terminal sessions. 

To configure, edit your Claude Code settings at `~/.claude/settings.json`:

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

---

## 2. Cursor

Cursor supports stdio MCP configurations natively.

1. Navigate to **Settings ➔ Features ➔ MCP**.
2. Click **+ Add New MCP Server**.
3. Configure:
   * **Name**: `aedile`
   * **Type**: `command`
   * **Command**: `python -m aedile`

---

## 3. Windsurf

Windsurf supports MCP servers configured via its `mcp_config.json`:

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

---

## 4. Other Agents (Devin, OpenCode, Antigravity)

For generic agents, invoke the server as a background subprocess using the command:
```bash
python -m aedile
```
The agent should direct its JSON-RPC messages to `stdin` and read responses from `stdout`. All system logging and diagnostic information is routed to `stderr` to avoid corrupting the communication channel.
