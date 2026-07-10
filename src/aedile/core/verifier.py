import copy
import os

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import Import, SourceFile, Violation
from aedile.core.parser import compute_module_name, os_path_root
from aedile.core.rules import BoundaryRule, CycleRule, LayerRule, NamingRule
from aedile.shared.config import Config


class ArchitectureVerifier:
    def __init__(self, config: Config) -> None:
        self.config = config

    def verify_changes(
        self,
        project_root: str,
        base_files: list[SourceFile],
        proposed_changes: list[dict],
    ) -> list[Violation]:
        """Simulates proposed file additions and modifications on top of the base files,

        rebuilds the import graph, runs architectural rules, and returns violations.
        """
        # Create a deep copy of base files to simulate modifications
        sim_files = {sf.relative_path: copy.deepcopy(sf) for sf in base_files}
        proposed_paths = set()

        for change in proposed_changes:
            rel_path = change.get("path")
            if not rel_path:
                continue

            # Standardize path separator to forward slash
            rel_path = rel_path.replace(os.sep, "/")

            # Path traversal prevention
            filepath = os.path.abspath(os.path.join(project_root, rel_path))
            safe_project_root = os.path.abspath(project_root)
            if (
                not filepath.startswith(safe_project_root + os.sep)
                and filepath != safe_project_root
            ):
                return [
                    Violation(
                        rule_name="security_check",
                        filepath=filepath,
                        relative_path=rel_path,
                        line=1,
                        message=f"Path traversal detected: {rel_path} escapes project root.",
                        confidence=1.0,
                        severity="error",
                    )
                ]

            proposed_paths.add(rel_path)
            action = change.get("action", "add")

            # Parse proposed imports
            imports = []
            for imp_name in change.get("imports", []):
                imports.append(Import(module=imp_name, names=[], line=1))

            if action == "add" or rel_path not in sim_files:
                # Simulate new file

                sim_files[rel_path] = SourceFile(
                    filepath=filepath,
                    relative_path=rel_path,
                    file_hash="simulated",
                    file_size=0,
                    language="python",
                    imports=imports,
                    symbols=[],
                )
            elif action == "modify":
                # Simulate modifying imports
                sf = sim_files[rel_path]
                sf.imports.extend(imports)

        simulated_files = list(sim_files.values())

        # Rebuild Graph
        graph = ArchitectureGraph()
        internal_modules = set()
        module_to_file_map = {}

        for sf in simulated_files:
            root = os_path_root(sf.filepath, sf.relative_path)
            module_name = compute_module_name(sf.filepath, root, self.config.src_dirs)
            internal_modules.add(module_name)
            module_to_file_map[module_name] = sf.filepath
            graph.add_node(module_name, sf.filepath)

        for sf in simulated_files:
            root = os_path_root(sf.filepath, sf.relative_path)
            source_module = compute_module_name(sf.filepath, root, self.config.src_dirs)

            for imp in sf.imports:
                target_module = None
                if imp.module in internal_modules:
                    target_module = imp.module
                else:
                    parts = imp.module.split(".")
                    for i in range(len(parts), 0, -1):
                        parent_pkg = ".".join(parts[:i])
                        if parent_pkg in internal_modules:
                            target_module = parent_pkg
                            break

                if target_module and target_module != source_module:
                    graph.add_edge(source_module, target_module)

        # Run rules
        violations: list[Violation] = []
        rules = [
            CycleRule(self.config),
            LayerRule(self.config),
            BoundaryRule(self.config),
            NamingRule(self.config),
        ]

        for rule in rules:
            try:
                rule_violations = rule.evaluate(simulated_files, graph)
                violations.extend(rule_violations)
            except Exception:
                pass

        # Filter violations to only keep those directly affecting or triggered by proposed changes
        filtered_violations = []
        proposed_modules = set()
        for p in proposed_paths:
            # Helper to get module name for proposed files
            filepath = os.path.abspath(os.path.join(project_root, p))
            proposed_modules.add(compute_module_name(filepath, project_root, self.config.src_dirs))

        for v in violations:
            # Check if relative path is in proposed changes
            if v.relative_path in proposed_paths:
                filtered_violations.append(v)
                continue

            # For cycle violations, check if any proposed module is part of the cycle message/cycle path
            if v.rule_name == "cycle_detection" and v.message:
                if any(m in v.message for m in proposed_modules):
                    filtered_violations.append(v)

        return filtered_violations
