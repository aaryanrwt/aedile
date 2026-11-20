import os
import re
from dataclasses import dataclass

from aedile.shared.config import Config

_DEBT_RE = re.compile(
    r"^\s*(#|//|/\*)\s*(shortcut|aedile-waive|ponytail)\s*:\s*(.+)$", re.IGNORECASE
)
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".aedile"}
_CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs"}


@dataclass
class DebtEntry:
    relative_path: str
    line: int
    marker: str
    summary: str
    ceiling: str
    upgrade_trigger: str
    has_trigger: bool


def scan_debt(
    project_root: str,
    config: Config | None = None,
    custom_marker: str | None = None,
) -> list[DebtEntry]:
    """Scans the repository for `# shortcut:` / `# aedile-waive:` debt markers.

    Flags entries missing an upgrade trigger (`no-trigger`) so deliberate
    simplifications never silently rot.
    """
    pattern = (
        re.compile(rf"^\s*(#|//|/\*)\s*({re.escape(custom_marker)})\s*:\s*(.+)$", re.IGNORECASE)
        if custom_marker
        else _DEBT_RE
    )

    entries: list[DebtEntry] = []
    abs_root = os.path.abspath(project_root)

    for root, dirs, files in os.walk(abs_root):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in sorted(files):
            _, ext = os.path.splitext(fname.lower())
            if ext not in _CODE_EXTS:
                continue
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, abs_root).replace(os.sep, "/")
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as f:
                    for idx, raw_line in enumerate(f, start=1):
                        m = pattern.search(raw_line.strip())
                        if not m:
                            continue
                        marker = m.group(2).lower()
                        body = m.group(3).strip().rstrip("*/").strip()
                        parts = [p.strip() for p in body.split(",", maxsplit=1)]
                        ceiling = parts[0]
                        trigger = parts[1] if len(parts) > 1 and parts[1] else ""
                        entries.append(
                            DebtEntry(
                                relative_path=rel_path,
                                line=idx,
                                marker=marker,
                                summary=body,
                                ceiling=ceiling,
                                upgrade_trigger=trigger,
                                has_trigger=bool(trigger),
                            )
                        )
            except OSError:
                continue

    return entries


def format_debt_ledger(entries: list[DebtEntry]) -> str:
    if not entries:
        return "No shortcut debt. Clean ledger."
    lines = ["### Aedile Architectural Debt Ledger"]
    no_trigger = 0
    for e in entries:
        tag = "" if e.has_trigger else " [no-trigger]"
        if not e.has_trigger:
            no_trigger += 1
        trig_str = f" | upgrade: {e.upgrade_trigger}" if e.upgrade_trigger else ""
        lines.append(f"- `{e.relative_path}:{e.line}` ({e.marker}): {e.ceiling}{trig_str}{tag}")
    lines.append(f"\n**Summary**: {len(entries)} markers, {no_trigger} with no trigger.")
    return "\n".join(lines)
