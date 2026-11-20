import os
import re
from collections import defaultdict

from aedile.core.models import SourceFile
from aedile.shared.config import Config

_SHARED_DIR_RE = re.compile(
    r"(shared|util|helper|lib|common|core|service|model|schema|domain|api)", re.IGNORECASE
)


def build_codebase_map(
    files: list[SourceFile],
    config: Config | None = None,
    budget_chars: int = 2000,
) -> str:
    """Builds a token-budgeted, AST-verified symbol & layer map of the repository.

    Prioritizes shared/core/utility directories first so AI assistants see reusable
    abstractions at session start without spending search tool calls.
    """
    if not files:
        return ""

    dir_symbols: dict[str, list[str]] = defaultdict(list)
    for sf in files:
        rel_dir = os.path.dirname(sf.relative_path).replace("\\", "/") or "."
        public_syms = [
            f"{s.parent_name}.{s.name}" if s.parent_name else s.name
            for s in sf.symbols
            if not s.is_private and s.kind in {"class", "function", "type_alias"}
        ]
        if public_syms:
            for sym_name in public_syms:
                if sym_name not in dir_symbols[rel_dir]:
                    dir_symbols[rel_dir].append(sym_name)

    if not dir_symbols:
        return ""

    def _layer_tag(directory: str) -> str:
        if not config or not config.layer_mappings:
            return ""
        for layer, patterns in config.layer_mappings.items():
            for pat in patterns:
                cleaned = pat.replace("**/", "").replace("/**", "").replace("*", "").strip("/")
                if cleaned and cleaned in directory:
                    return f" [{layer}]"
        return ""

    # Sort shared/core directories first, then alphabetically
    sorted_dirs = sorted(
        dir_symbols.keys(),
        key=lambda d: (0 if _SHARED_DIR_RE.search(d) else 1, d),
    )

    lines: list[str] = []
    used = 0
    skipped = 0
    for d in sorted_dirs:
        syms = dir_symbols[d]
        cap = 15 if len(syms) > 15 else len(syms)
        shown = ", ".join(syms[:cap])
        suffix = ", ..." if len(syms) > cap else ""
        tag = _layer_tag(d)
        line = f"{d}/{tag}: {shown}{suffix}"
        if used + len(line) + 1 > budget_chars and lines:
            skipped += 1
            continue
        lines.append(line)
        used += len(line) + 1

    header = "Aedile AST Codebase Map (reuse existing symbols; read a file only for details):\n"
    footer = (
        f"\n({skipped} more directories omitted by {budget_chars}-char budget)" if skipped else ""
    )
    return header + "\n".join(lines) + footer
