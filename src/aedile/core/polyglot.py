import hashlib
import json
import os
import re

from aedile.core.models import Import, SourceFile, Symbol
from aedile.core.parser import BaseParser, compute_module_name
from aedile.shared.errors import ParserError

_TS_IMPORT_RE = re.compile(
    r"""^\s*import\s+(?:type\s+)?(?:[\w*{},\s]+\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_TS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_TS_EXPORT_RE = re.compile(
    r"""^\s*export\s+(?:default\s+)?(?:async\s+)?(function\*?|class|const|let|interface|type|enum)\s+([A-Za-z_$][\w$]*)""",
    re.MULTILINE,
)

_GO_IMPORT_SINGLE_RE = re.compile(r"""^\s*import\s+(?:[\w.]+\s+)?"([^"]+)\"""", re.MULTILINE)
_GO_IMPORT_BLOCK_RE = re.compile(r"""import\s*\((.*?)\)""", re.DOTALL)
_GO_IMPORT_LINE_RE = re.compile(r"""(?:[\w.]+\s+)?"([^"]+)\"""")
_GO_SYMBOL_RE = re.compile(
    r"""^\s*(?:func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)|type\s+([A-Z]\w*))""", re.MULTILINE
)

_RUST_USE_RE = re.compile(r"""^\s*(?:pub\s+)?use\s+([^;]+);""", re.MULTILINE)
_RUST_MOD_RE = re.compile(r"""^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;""", re.MULTILINE)
_RUST_SYM_RE = re.compile(
    r"""^\s*pub(?:\([^)]*\))?\s+(?:async\s+)?(fn|struct|enum|trait|type)\s+(\w+)""",
    re.MULTILINE,
)


def _line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _load_tsconfig_aliases(project_root: str) -> dict[str, str]:
    tsconfig = os.path.join(project_root, "tsconfig.json")
    if not os.path.exists(tsconfig):
        return {}
    try:
        with open(tsconfig, encoding="utf-8", errors="ignore") as f:
            raw = re.sub(r"//.*|/\*.*?\*/", "", f.read(), flags=re.DOTALL)
        data = json.loads(raw)
        paths = data.get("compilerOptions", {}).get("paths", {})
        aliases: dict[str, str] = {}
        for k, v in paths.items():
            if isinstance(v, list) and v:
                aliases[k.rstrip("*")] = str(v[0]).rstrip("*")
        return aliases
    except Exception:
        return {}


def _resolve_js_import(
    raw_spec: str,
    filepath: str,
    project_root: str,
    src_dirs: list[str],
    aliases: dict[str, str],
) -> tuple[str, bool]:
    """Resolves relative JS/TS imports and tsconfig path aliases into canonical module names."""
    spec = raw_spec
    for prefix, target in aliases.items():
        if spec.startswith(prefix):
            spec = target + spec[len(prefix) :]
            break

    is_rel = spec.startswith(".")
    if is_rel:
        target_path = os.path.normpath(os.path.join(os.path.dirname(filepath), spec))
        if not os.path.splitext(target_path)[1]:
            target_path = target_path + ".js"
        return compute_module_name(target_path, project_root, src_dirs), True

    return spec.replace("/", "."), False


class PolyglotParser(BaseParser):
    """Structural parser for TypeScript, JavaScript, Go, and Rust into SourceFile IR."""

    def __init__(self, language: str) -> None:
        self.language = language

    def parse(self, filepath: str, project_root: str, src_dirs: list[str]) -> SourceFile:
        if not os.path.exists(filepath):
            raise ParserError(f"File not found: {filepath}")
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()

        st = os.stat(filepath)
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        relative_path = os.path.relpath(filepath, project_root).replace(os.sep, "/")

        imports: list[Import] = []
        symbols: list[Symbol] = []

        if self.language in {"javascript", "typescript"}:
            aliases = _load_tsconfig_aliases(project_root)
            for m in _TS_IMPORT_RE.finditer(content):
                mod, is_rel = _resolve_js_import(
                    m.group(1), filepath, project_root, src_dirs, aliases
                )
                imports.append(
                    Import(
                        module=mod,
                        names=[],
                        line=_line_of_offset(content, m.start()),
                        is_relative=is_rel,
                    )
                )
            for m in _TS_REQUIRE_RE.finditer(content):
                mod, is_rel = _resolve_js_import(
                    m.group(1), filepath, project_root, src_dirs, aliases
                )
                imports.append(
                    Import(
                        module=mod,
                        names=[],
                        line=_line_of_offset(content, m.start()),
                        is_relative=is_rel,
                    )
                )
            for m in _TS_EXPORT_RE.finditer(content):
                kind = "class" if m.group(1) == "class" else "function"
                line_no = _line_of_offset(content, m.start())
                symbols.append(
                    Symbol(
                        name=m.group(2),
                        kind=kind,
                        line=line_no,
                        end_line=line_no,
                        is_private=False,
                    )
                )

        elif self.language == "go":
            for m in _GO_IMPORT_SINGLE_RE.finditer(content):
                imports.append(
                    Import(module=m.group(1), names=[], line=_line_of_offset(content, m.start()))
                )
            for blk in _GO_IMPORT_BLOCK_RE.finditer(content):
                base_line = _line_of_offset(content, blk.start())
                for idx, line in enumerate(blk.group(1).splitlines()):
                    lm = _GO_IMPORT_LINE_RE.search(line)
                    if lm:
                        imports.append(Import(module=lm.group(1), names=[], line=base_line + idx))
            for m in _GO_SYMBOL_RE.finditer(content):
                name = m.group(1) or m.group(2)
                kind = "function" if m.group(1) else "class"
                line_no = _line_of_offset(content, m.start())
                symbols.append(
                    Symbol(name=name, kind=kind, line=line_no, end_line=line_no, is_private=False)
                )

        elif self.language == "rust":
            for m in _RUST_USE_RE.finditer(content):
                mod = m.group(1).split("::{", 1)[0].strip().replace("::", ".")
                imports.append(
                    Import(module=mod, names=[], line=_line_of_offset(content, m.start()))
                )
            for m in _RUST_MOD_RE.finditer(content):
                imports.append(
                    Import(module=m.group(1), names=[], line=_line_of_offset(content, m.start()))
                )
            for m in _RUST_SYM_RE.finditer(content):
                kind = "function" if m.group(1) == "fn" else "class"
                line_no = _line_of_offset(content, m.start())
                symbols.append(
                    Symbol(
                        name=m.group(2),
                        kind=kind,
                        line=line_no,
                        end_line=line_no,
                        is_private=False,
                    )
                )

        return SourceFile(
            filepath=filepath,
            relative_path=relative_path,
            file_hash=file_hash,
            file_size=st.st_size,
            language=self.language,
            imports=imports,
            symbols=symbols,
            mtime_ns=st.st_mtime_ns,
        )
