import os
import re

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.rules.base import BaseRule


class DeadCodeRule(BaseRule):
    @property
    def name(self) -> str:
        return "dead_code_detection"

    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        violations: list[Violation] = []
        if not self.config.dead_code_detection:
            return violations

        # First, build a map of all defined symbols: (module_name, symbol_name) -> Symbol
        from aedile.core.parser import compute_module_name, os_path_root

        # We keep track of which files are test files or examples so we can treat them differently
        # (e.g., symbols defined in tests don't count as dead, and symbols used in tests might still be dead in src,
        # but to be safe, we check usage in all non-test files first).

        defined_symbols = []
        # A lookup map of file paths to contents for regex searches
        file_contents = {}

        for sf in files:
            # Skip reading content if file is very large or doesn't exist
            if not os.path.exists(sf.filepath):
                continue

            try:
                with open(sf.filepath, encoding="utf-8", errors="replace") as f:
                    file_contents[sf.filepath] = f.read()
            except Exception:
                continue

            # Skip checking symbols defined in tests or examples or setup files
            is_test_or_example = (
                "test" in sf.relative_path
                or "example" in sf.relative_path
                or "setup.py" in sf.filepath
            )
            if is_test_or_example:
                continue

            root = os_path_root(sf.filepath, sf.relative_path)
            module_name = compute_module_name(sf.filepath, root, self.config.src_dirs)

            for sym in sf.symbols:
                # Exclude main function, dunders, visitor hooks, or class methods called via self
                if (
                    sym.name in ["main", "app"]
                    or sym.name.startswith("__")
                    or sym.name.startswith("visit_")
                    or sym.kind == "method"
                ):
                    continue
                # Exclude private functions unless we want strict checking, but let's check them inside the same file.
                # Actually, private symbols (like `_helper`) are used if they appear elsewhere in the SAME file!
                if sym.is_private:
                    # Check if referenced in the same file (more than once, since definition is once)
                    content = file_contents.get(sf.filepath, "")
                    matches = re.findall(r"\b" + re.escape(sym.name) + r"\b", content)
                    if len(matches) <= 1:  # Only defined, never called
                        violations.append(
                            Violation(
                                rule_name=self.name,
                                filepath=sf.filepath,
                                relative_path=sf.relative_path,
                                line=sym.line,
                                message=f"Dead abstraction: Private symbol '{sym.name}' is defined but never used in the file.",
                                offending_symbol=sym.name,
                                confidence=0.9,
                                severity="warning",
                            )
                        )
                else:
                    defined_symbols.append((sf, module_name, sym))

        # Pre-index identifier occurrences and module imports in O(total_tokens) instead of O(symbols * files).
        ident_files: dict[str, set[str]] = {}
        wildcard_importers: dict[str, set[str]] = {}
        for sf_other in files:
            content_other = file_contents.get(sf_other.filepath, "")
            if content_other:
                for tok in set(re.findall(r"\b\w+\b", content_other)):
                    ident_files.setdefault(tok, set()).add(sf_other.filepath)
            for imp in sf_other.imports:
                if not imp.names:
                    wildcard_importers.setdefault(imp.module, set()).add(sf_other.filepath)

        # Check usages for public symbols in other files
        for sf_def, mod_def, sym in defined_symbols:
            ref_files = ident_files.get(sym.name)
            is_used = bool(ref_files and any(fp != sf_def.filepath for fp in ref_files))
            if not is_used:
                # Fallback: check wildcard/module-level imports
                for mod_key, importers in wildcard_importers.items():
                    if mod_key == mod_def or mod_key.startswith(mod_def + "."):
                        if any(fp != sf_def.filepath for fp in importers):
                            is_used = True
                            break

            if not is_used:
                violations.append(
                    Violation(
                        rule_name=self.name,
                        filepath=sf_def.filepath,
                        relative_path=sf_def.relative_path,
                        line=sym.line,
                        message=f"Dead abstraction: Public symbol '{sym.name}' is defined but never referenced in the project.",
                        offending_symbol=sym.name,
                        confidence=0.8,
                        severity="warning",
                    )
                )

        return violations
