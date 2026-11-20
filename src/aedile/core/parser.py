import abc
import ast
import hashlib
import os

from aedile.core.models import Import, SourceFile, Symbol
from aedile.shared.errors import ParserError


class BaseParser(abc.ABC):
    @abc.abstractmethod
    def parse(self, filepath: str, project_root: str, src_dirs: list[str]) -> SourceFile:
        """Parses a source file and returns a SourceFile domain model."""
        pass


def compute_module_name(filepath: str, project_root: str, src_dirs: list[str]) -> str:
    """Computes the fully-qualified Python module name for a given file path.

    Example:
      filepath: /project/src/aedile/core/scanner.py
      src_dirs: [/project/src]
      returns: aedile.core.scanner
    """
    abs_filepath = os.path.abspath(filepath)
    # Find the matching source directory
    matched_src_dir = None
    for src_dir in src_dirs:
        abs_src_dir = os.path.abspath(
            os.path.join(project_root, src_dir) if not os.path.isabs(src_dir) else src_dir
        )
        if abs_filepath.startswith(abs_src_dir):
            matched_src_dir = abs_src_dir
            break

    if matched_src_dir:
        rel_path = os.path.relpath(abs_filepath, matched_src_dir)
    else:
        rel_path = os.path.relpath(abs_filepath, project_root)

    # Remove extension and split path
    base, _ = os.path.splitext(rel_path)
    parts = base.split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(p for p in parts if p)


def resolve_relative_import(source_module: str, level: int, module_name: str | None) -> str:
    """Resolves a relative import (e.g. level=1, module_name='models' inside 'aedile.core.scanner')
    to its absolute module name 'aedile.core.models'.
    """
    parts = source_module.split(".")
    if level > len(parts):
        # Fallback to module name if we go beyond root
        return module_name or ""

    base_parts = parts[:-level] if level > 0 else parts
    if module_name:
        base_parts.append(module_name)
    return ".".join(base_parts)


class PythonParser(BaseParser):
    def parse(self, filepath: str, project_root: str, src_dirs: list[str]) -> SourceFile:
        if not os.path.exists(filepath):
            raise ParserError(f"File not found: {filepath}")

        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            raise ParserError(f"Failed to read file {filepath}: {e}")

        # Compute file hash, size, and mtime_ns
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        stat = os.stat(filepath)
        file_size = stat.st_size
        mtime_ns = stat.st_mtime_ns
        relative_path = os.path.relpath(filepath, project_root).replace(os.sep, "/")

        # Compute source module name for relative import resolution
        source_module = compute_module_name(filepath, project_root, src_dirs)

        imports: list[Import] = []
        symbols: list[Symbol] = []

        try:
            tree = ast.parse(content, filepath)
        except SyntaxError as e:
            # Create a shell SourceFile to record syntax error or raise
            raise ParserError(f"Syntax error in {filepath}:{e.lineno}: {e.msg}")
        except Exception as e:
            raise ParserError(f"Failed to AST parse file {filepath}: {e}")

        class ASTVisitor(ast.NodeVisitor):
            def visit_Import(self, node: ast.Import) -> None:
                is_lazy = bool(getattr(node, "is_lazy", 0))
                for alias in node.names:
                    imports.append(
                        Import(
                            module=alias.name,
                            names=[],
                            line=node.lineno,
                            alias=alias.asname,
                            is_relative=False,
                            is_lazy=is_lazy,
                        )
                    )
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                is_relative = node.level > 0
                is_lazy = bool(getattr(node, "is_lazy", 0))
                imported_module = node.module or ""

                # Resolve relative import
                if is_relative:
                    module_path = resolve_relative_import(
                        source_module, node.level, imported_module
                    )
                else:
                    module_path = imported_module

                names = [alias.name for alias in node.names]
                imports.append(
                    Import(
                        module=module_path,
                        names=names,
                        line=node.lineno,
                        is_relative=is_relative,
                        is_lazy=is_lazy,
                    )
                )
                self.generic_visit(node)

            def _format_sig(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
                args = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
                if node.args.vararg:
                    args.append(f"*{node.args.vararg.arg}")
                if node.args.kwarg:
                    args.append(f"**{node.args.kwarg.arg}")
                ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                return f"({', '.join(args)}){ret}"

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                docstring = ast.get_docstring(node)
                symbols.append(
                    Symbol(
                        name=node.name,
                        kind="class",
                        line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        docstring=docstring,
                        is_private=node.name.startswith("_"),
                    )
                )
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(
                            Symbol(
                                name=item.name,
                                kind="method",
                                line=item.lineno,
                                end_line=getattr(item, "end_lineno", item.lineno),
                                docstring=ast.get_docstring(item),
                                is_private=item.name.startswith("_"),
                                signature=self._format_sig(item),
                                parent_name=node.name,
                            )
                        )
                self.generic_visit(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                is_toplevel = (
                    isinstance(getattr(node, "parent", None), ast.Module) or node.col_offset == 0
                )
                if is_toplevel:
                    docstring = ast.get_docstring(node)
                    symbols.append(
                        Symbol(
                            name=node.name,
                            kind="function",
                            line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            docstring=docstring,
                            is_private=node.name.startswith("_"),
                            signature=self._format_sig(node),
                        )
                    )
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                is_toplevel = (
                    isinstance(getattr(node, "parent", None), ast.Module) or node.col_offset == 0
                )
                if is_toplevel:
                    docstring = ast.get_docstring(node)
                    symbols.append(
                        Symbol(
                            name=node.name,
                            kind="function",
                            line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            docstring=docstring,
                            is_private=node.name.startswith("_"),
                            signature=self._format_sig(node),
                        )
                    )
                self.generic_visit(node)

            def visit_Assign(self, node: ast.Assign) -> None:
                if isinstance(getattr(node, "parent", None), ast.Module):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 1:
                            symbols.append(
                                Symbol(
                                    name=target.id,
                                    kind="constant",
                                    line=node.lineno,
                                    end_line=getattr(node, "end_lineno", node.lineno),
                                    is_private=target.id.startswith("_"),
                                )
                            )
                self.generic_visit(node)

            def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
                if isinstance(getattr(node, "parent", None), ast.Module):
                    symbols.append(
                        Symbol(
                            name=node.name.id,
                            kind="type_alias",
                            line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            is_private=node.name.id.startswith("_"),
                        )
                    )
                self.generic_visit(node)

        # Set parent reference to detect top-level functions easily
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent  # type: ignore[attr-defined]

        visitor = ASTVisitor()
        visitor.visit(tree)

        return SourceFile(
            filepath=filepath,
            relative_path=relative_path,
            file_hash=file_hash,
            file_size=file_size,
            language="python",
            imports=imports,
            symbols=symbols,
            mtime_ns=mtime_ns,
        )


class LanguageDetector:
    @staticmethod
    def detect(filepath: str) -> str:
        _, ext = os.path.splitext(filepath.lower())
        if ext == ".py":
            return "python"
        elif ext in [".js", ".jsx"]:
            return "javascript"
        elif ext in [".ts", ".tsx"]:
            return "typescript"
        elif ext == ".go":
            return "go"
        elif ext == ".rs":
            return "rust"
        return "unknown"


def os_path_root(filepath: str, relative_path: str) -> str:
    """Computes the project root given absolute filepath and relative path.
    Example:
      filepath: /workspace/project/src/main.py
      relative_path: src/main.py
      returns: /workspace/project
    """
    abs_file = filepath.replace("\\", "/")
    rel_file = relative_path.replace("\\", "/")

    if abs_file.endswith(rel_file):
        root = abs_file[: -len(rel_file)]
        return root.rstrip("/")
    return os.path.dirname(filepath)
