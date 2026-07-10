import fnmatch
import os

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.rules.base import BaseRule


class NamingRule(BaseRule):
    @property
    def name(self) -> str:
        return "naming_conventions"

    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        violations: list[Violation] = []
        if not self.config.naming_conventions or not self.config.naming_patterns:
            return violations

        for sf in files:
            norm_path = sf.relative_path.replace(os.sep, "/")
            filename = os.path.basename(sf.filepath)

            # Check all matching naming rules
            for rule in self.config.naming_patterns:
                if fnmatch.fnmatch(norm_path, rule.path_pattern):
                    # Validate file name pattern
                    if rule.file_pattern and not rule.matches_file(filename):
                        violations.append(
                            Violation(
                                rule_name=self.name,
                                filepath=sf.filepath,
                                relative_path=sf.relative_path,
                                line=1,
                                message=(
                                    f"Naming violation: File name '{filename}' does not match "
                                    f"required pattern '{rule.file_pattern}' for path '{rule.path_pattern}'."
                                ),
                                offending_symbol=filename,
                                confidence=1.0,
                                severity="warning",
                            )
                        )

                    # Validate symbols inside the file
                    for sym in sf.symbols:
                        if sym.kind == "class" and rule.class_pattern:
                            if not rule.matches_class(sym.name):
                                violations.append(
                                    Violation(
                                        rule_name=self.name,
                                        filepath=sf.filepath,
                                        relative_path=sf.relative_path,
                                        line=sym.line,
                                        message=(
                                            f"Naming violation: Class '{sym.name}' does not match "
                                            f"required pattern '{rule.class_pattern}' for path '{rule.path_pattern}'."
                                        ),
                                        offending_symbol=sym.name,
                                        confidence=1.0,
                                        severity="warning",
                                    )
                                )
                        elif sym.kind == "function" and rule.function_pattern:
                            # Skip double-underscore functions/methods (e.g. __init__)
                            if sym.name.startswith("__") and sym.name.endswith("__"):
                                continue
                            if not rule.matches_function(sym.name):
                                violations.append(
                                    Violation(
                                        rule_name=self.name,
                                        filepath=sf.filepath,
                                        relative_path=sf.relative_path,
                                        line=sym.line,
                                        message=(
                                            f"Naming violation: Function '{sym.name}' does not match "
                                            f"required pattern '{rule.function_pattern}' for path '{rule.path_pattern}'."
                                        ),
                                        offending_symbol=sym.name,
                                        confidence=1.0,
                                        severity="warning",
                                    )
                                )

        return violations
