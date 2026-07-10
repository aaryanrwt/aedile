from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.rules.base import BaseRule


class CycleRule(BaseRule):
    @property
    def name(self) -> str:
        return "cycle_detection"

    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        violations: list[Violation] = []
        if not self.config.cycle_detection:
            return violations

        cycles = graph.find_all_cycles()
        if not cycles:
            return violations

        # Map module name to SourceFile for quick lookup
        module_to_file_map = {}
        for sf in files:
            # Recompute module name to match graph nodes
            from aedile.core.parser import compute_module_name, os_path_root
            m_name = compute_module_name(sf.filepath, os_path_root(sf.filepath, sf.relative_path), self.config.src_dirs)
            module_to_file_map[m_name] = sf

        for cycle in cycles:
            cycle_len = len(cycle)
            # For each step in the cycle: node_a -> node_b
            for i in range(cycle_len):
                node_a = cycle[i]
                node_b = cycle[(i + 1) % cycle_len]

                sf_a = module_to_file_map.get(node_a)
                if not sf_a:
                    continue

                # Find the import statement in A that imports B
                for imp in sf_a.imports:
                    # Match if the imported module matches B or starts with B (e.g. B.submodule)
                    if imp.module == node_b or imp.module.startswith(node_b + "."):
                        cycle_path = " -> ".join(cycle) + f" -> {cycle[0]}"
                        violations.append(
                            Violation(
                                rule_name=self.name,
                                filepath=sf_a.filepath,
                                relative_path=sf_a.relative_path,
                                line=imp.line,
                                message=(
                                    f"Dependency cycle detected: {cycle_path}. "
                                    f"Module '{node_a}' imports '{imp.module}' on line {imp.line}."
                                ),
                                offending_symbol=imp.module,
                                confidence=1.0,
                                severity="error",
                            )
                        )
                        break # Only report once per file per cycle

        return violations

