<p align="center">
  <img src="images/logo.png" alt="Aedile Logo" width="180"/>
</p>

# Aedile

> Before an AI writes code, it should prove that the code deserves to exist.

**Aedile** is an engineering intelligence layer for AI coding agents. Operating locally as a zero-dependency Stdio MCP Server, it intercepts an AI agent’s plans before code generation begins—guiding agents to reuse existing codebase patterns, leverage standard libraries, and enforce layer boundaries.

[![PyPI version](https://img.shields.io/pypi/v/aedile.svg?color=3B82F6)](https://pypi.org/project/aedile/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/DietrichGebert/aedile/ci.yml?branch=main)](https://github.com/DietrichGebert/aedile/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

---

## 1. The Problem

AI coding assistants are good at generating code quickly. They are much less reliable at deciding whether new code is necessary or whether similar functionality already exists.

Because LLMs reason in a vacuum, they frequently:
* **Duplicate helpers**: Re-write existing utility methods because they do not know they exist.
* **Violate layering boundaries**: Introduce circular imports or break separation of concerns.
* **Inflate context windows**: Consume excessive token overhead planning and writing over-engineered logic.

Aedile changes the agent's default behavior from *code generation* to *abstractions reuse*.

---

## 2. How it Works

Aedile hooks into the AI agent's planning turn via the Model Context Protocol (MCP). Before code is written, Aedile evaluates the proposed changes:

```text
User prompt ➔ AI starts planning ➔ Aedile intercepts (MCP) ➔ Checks repository ➔ Checks architecture ➔ Checks existing abstractions ➔ Checks standard library ➔ Checks dependencies ➔ Returns advice ➔ AI writes code
```

We designed Aedile to enforce a structured [Decision Ladder](docs/DECISION_LADDER.md)—directing the agent to exhaustively check codebase reuse, standard libraries, and pre-installed dependencies before drafting new logic.

---

## 3. Quick Example: Adding JWT Token Generation

### Standard AI Agent
The agent plans to write a custom JWT helper, unaware that `src/shared/auth.py` already contains a token generator. It installs a new library, adds 40 lines of wrapper code, and increases reasoning costs.

### With Aedile
The agent consults Aedile during its planning step:

```text
AI:     "I'm going to create jwt.py."
Aedile: "Existing helper found: src/shared/auth.py. Reuse create_token()."
AI:     "Understood. Importing src.shared.auth and writing 1 line instead of 40."
```

By querying Aedile, the agent avoids duplicate work, preserves the codebase architecture, and reduces reasoning token usage.

---

## 4. Installation & Setup

First, generate the prompt templates (`.cursorrules` and `.claudeprompt`) in your workspace matching your layer settings:
```bash
python -m aedile compile-rules
```

Then register Aedile as an MCP server:

### Claude Code (`~/.claude/settings.json`)
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

### Cursor (`Settings ➔ Features ➔ MCP`)
* **Name**: `aedile`
* **Type**: `command`
* **Command**: `python -m aedile`

*See [SUPPORTED_AGENTS.md](SUPPORTED_AGENTS.md) for more details.*

---

## 5. Benchmarks

We measured the execution of backend engineering tasks (such as token authentication and endpoint refactoring) across multiple runs. Full parameters are documented in [results.json](benchmarks/results.json) and compiled in [BENCHMARKS.md](benchmarks/BENCHMARKS.md).

| Metric | Without Aedile | Prompt-Only Rules | With Aedile |
| :--- | :---: | :---: | :---: |
| **Reasoning Cost (Avg Tokens)** | 1,850 | 1,100 | **350** |
| **Context Window Size (Tokens)** | 4,200 | 5,100 | **1,200** |
| **Duplicate Code Written** | Yes | Yes | **No** |
| **Tool Calls Executed** | 3 | 2 | **1** |

---

## 6. Paradigm Comparison

Aedile represents a shift in how codebase constraints are enforced:

* **Static Prompting vs. Dynamic Context**: Static prompts (like `.cursorrules` text) decay and suffer from "prompt drift" in long sessions. Aedile queries real-time codebase symbols and active dependencies dynamically via a single MCP tool (`aedile_consult`).
* **Post-Facto Linters vs. In-Plan Verification**: Traditional linters check imports after files are saved, failing in CI/CD. Aedile verifies planned imports in-memory before files are written, letting the model self-correct.

### Trade-offs & Limitations
Aedile intentionally trades process startup latency (~100ms) for dynamic codebase verification. We optimized traversal by using SHA-256 increment caching, keeping scan times under 40ms. Symbol parsing is currently optimized for Python workspaces, with TypeScript/JavaScript support planned next.

---

## 7. Contributing

We welcome contributions to Aedile. Please review our [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details on code style, testing, and pull requests.

---

## 8. License

Aedile is open-source software licensed under the [MIT License](LICENSE).

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=DietrichGebert/aedile&type=Date)](https://star-history.com/#DietrichGebert/aedile&Date)
