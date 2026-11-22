"""Environment and configuration diagnostics (`aedile doctor`)."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass


@dataclass
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def run_doctor(project_root: str) -> list[DoctorCheck]:
    abs_root = os.path.abspath(project_root)
    checks: list[DoctorCheck] = []

    py_ok = sys.version_info >= (3, 13)
    checks.append(
        DoctorCheck(
            name="python",
            ok=py_ok,
            detail=f"{sys.version.split()[0]} ({'supported' if py_ok else 'requires >=3.13'})",
        )
    )

    for tool in ("git", "ruff", "mypy", "pytest"):
        found = shutil.which(tool)
        checks.append(
            DoctorCheck(
                name=tool,
                ok=bool(found),
                detail=found or "not found on PATH",
            )
        )

    for rel in (
        "aedile.toml",
        ".aedile/cache.json",
        ".aedile/baseline.json",
        ".mcp.json",
        ".cursor/mcp.json",
    ):
        full = os.path.join(abs_root, rel)
        checks.append(
            DoctorCheck(
                name=rel,
                ok=os.path.exists(full),
                detail="present" if os.path.exists(full) else "not configured",
            )
        )

    return checks


def format_doctor(checks: list[DoctorCheck]) -> str:
    lines = ["### Aedile Doctor"]
    for c in checks:
        tag = "OK" if c.ok else "WARN"
        lines.append(f"- [{tag}] {c.name}: {c.detail}")
    return "\n".join(lines)
