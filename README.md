<p align="center">
  <img src="images/logo.png" alt="Aedile Logo" width="160"/>
</p>

<h1 align="center">Aedile</h1>

<p align="center">
  <strong>Before an AI writes code, it should prove that the code deserves to exist.</strong>
</p>

<p align="center">
  <a href="https://github.com/aaryanrwt/aedile/actions/workflows/ci.yml">
    <img src="https://github.com/aaryanrwt/aedile/actions/workflows/ci.yml/badge.svg?branch=release/v1.0-validation" alt="CI Status"/>
  </a>
  <a href="https://pypi.org/project/aedile/">
    <img src="https://img.shields.io/pypi/v/aedile.svg" alt="PyPI Version"/>
  </a>
  <a href="https://pypi.org/project/aedile/">
    <img src="https://img.shields.io/pypi/dm/aedile.svg" alt="PyPI Downloads"/>
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/pypi/pyversions/aedile.svg" alt="Python Versions"/>
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/pypi/l/aedile.svg" alt="License: MIT"/>
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="Code Style: Ruff"/>
  </a>
</p>

<p align="center">
Aedile is an engineering intelligence layer for AI coding assistants. It analyzes your codebase before implementation begins, helping agents reuse existing code, enforce architecture boundaries, prefer standard libraries, and avoid unnecessary complexity—all without sending a single byte outside your machine.
</p>

---

```
          Claude Code
               │
               ▼
        "Build authentication"
               │
               ▼
           Aedile MCP
      ┌────────────────────┐
      │ Existing helper?   │
      │ Stdlib available?  │
      │ Import cycles?     │
      │ Layer violation?   │
      └────────────────────┘
               │
               ▼
      Minimal implementation
```

---

## Why Aedile?

Modern coding assistants know how to write code. They usually don't know your architecture.

That leads to:

- duplicate utilities
- unnecessary dependencies
- circular imports
- broken layering
- inconsistent implementations

Aedile verifies the repository before code generation begins, giving coding assistants real project context instead of relying solely on prompts.

---

## Quick Example

**Without Aedile**

```
AI: "I'll install requests."

↓

Repository already has httpx.

↓

Duplicate dependency.
```

**With Aedile**

```
AI: "Repository already uses httpx."

↓

Reuse existing client.

↓

No duplicate dependency.
```

---

## How It Works

Aedile implements the Model Context Protocol (MCP). The assistant calls a single tool—`aedile_consult`—before generating any code.

```
Developer
    │
    ▼
  Claude
    │
    ▼
Aedile MCP
    │
    ├── Architecture Verifier
    ├── Workspace Index
    └── Decision Engine
    │
    ▼
  Advice
    │
    ▼
  Claude
    │
    ▼
Implementation
```

Aedile never modifies your code. It only observes and advises.

---

## Installation

```bash
pip install aedile
```

Generate the local prompt templates:

```bash
python -m aedile compile-rules
```

Then add `python -m aedile` as an MCP server in your coding assistant. See [SUPPORTED_AGENTS.md](SUPPORTED_AGENTS.md) for step-by-step guides.

---

## Configuration

Aedile works out of the box with zero configuration. Advanced options are documented in [CONFIGURATION.md](CONFIGURATION.md).

---

## Supported Agents

| Agent | Status |
|---|---|
| Claude Code | ✓ Supported |
| Cursor | ✓ Supported |
| Windsurf | ✓ Supported |
| Continue | ✓ Supported |

Full setup guides are in [SUPPORTED_AGENTS.md](SUPPORTED_AGENTS.md).

---

## Benchmarks

Benchmarks were measured using identical prompts on the same repository, before and after enabling Aedile.

**Environment**

- Hardware: Apple M2 Pro, 16 GB RAM
- Python: 3.11
- Agent: Claude 2.1
- Repository: 42 modules, ~8,000 lines of Python

**Results**

| Metric | Without Aedile | With Aedile |
|---|---|---|
| Reasoning Cost (avg tokens) | 1,850 | **350** |
| Context Window (tokens) | 4,200 | **1,200** |
| Duplicate Code Written | Yes | **No** |
| Tool Calls Executed | 3 | **1** |

Full methodology and raw data: [BENCHMARKS.md](benchmarks/BENCHMARKS.md).

---

## FAQ

**Why not use static prompting (e.g., `.cursorrules`)?**

Static prompts drift. As the context window fills, the model's adherence to static text degrades. Aedile enforces constraints through a live tool interface—the model receives current repository facts on every call, not instructions it may ignore.

**Does Aedile require internet access?**

No. All scanning, indexing, and analysis runs locally. There is no outbound network traffic and no telemetry.

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Decision Ladder](docs/DECISION_LADDER.md)
- [Supported Agents](SUPPORTED_AGENTS.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [Security Policy](SECURITY.md)

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a pull request.

---

## License

Aedile is released under the [MIT License](LICENSE).
