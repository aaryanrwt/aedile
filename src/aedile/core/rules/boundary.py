from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.rules.base import BaseRule


class BoundaryRule(BaseRule):
    @property
    def name(self) -> str:
        return "module_boundaries"

    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        violations: list[Violation] = []
        if not self.config.module_boundaries:
            return violations

        # Map filepath to its module path
        from aedile.core.parser import compute_module_name, os_path_root

        for sf in files:
            root = os_path_root(sf.filepath, sf.relative_path)
            source_module = compute_module_name(sf.filepath, root, self.config.src_dirs)
            source_parts = source_module.split(".")

            for imp in sf.imports:
                target_module = imp.module
                target_parts = target_module.split(".")

                # Check if the target module path contains a private segment (e.g. '_private' or 'internal')
                private_idx = -1
                for idx, part in enumerate(target_parts):
                    # Check if part starts with private prefix
                    is_private_seg = any(
                        part.startswith(prefix) for prefix in self.config.private_prefixes
                    )
                    # Also check for explicit "internal" segments
                    if is_private_seg or part == "internal":
                        private_idx = idx
                        break

                if private_idx != -1:
                    # The private parent is the module path up to the private segment
                    # E.g. 'aedile.core.rules._private.helper' -> parent prefix is 'aedile.core.rules'
                    allowed_parent_prefix = ".".join(target_parts[:private_idx])

                    # Source module must start with this parent prefix to be allowed
                    source_prefix = ".".join(source_parts)
                    if not source_prefix.startswith(allowed_parent_prefix):
                        violations.append(
                            Violation(
                                rule_name=self.name,
                                filepath=sf.filepath,
                                relative_path=sf.relative_path,
                                line=imp.line,
                                message=(
                                    f"Module boundary violation: Module '{target_module}' is private "
                                    f"to '{allowed_parent_prefix}'. "
                                    f"It cannot be imported by '{source_module}'."
                                ),
                                offending_symbol=target_module,
                                confidence=1.0,
                                severity="error",
                            )
                        )

        return violations
