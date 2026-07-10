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
                # Exclude main function, private symbols, or dunders
                if sym.name in ["main", "app"] or sym.name.startswith("__"):
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

        # Check usages for public symbols in other files
        for sf_def, mod_def, sym in defined_symbols:
            is_used = False

            # Check if explicitly imported or referenced by name in any OTHER file
            for sf_other in files:
                if sf_other.filepath == sf_def.filepath:
                    continue

                # 1. Check explicit import
                for imp in sf_other.imports:
                    # Imports the module containing the symbol
                    if imp.module == mod_def or imp.module.startswith(mod_def + "."):
                        if not imp.names or sym.name in imp.names:
                            is_used = True
                            break
                if is_used:
                    break

                # 2. Check text reference (token word boundary match)
                content_other = file_contents.get(sf_other.filepath, "")
                if content_other and re.search(r"\b" + re.escape(sym.name) + r"\b", content_other):
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
