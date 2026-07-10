import fnmatch
import hashlib
import os
import time

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import ProjectMetrics, Report, SourceFile, Violation
from aedile.core.parser import PythonParser, compute_module_name, os_path_root
from aedile.core.rules import (
    BoundaryRule,
    CycleRule,
    DeadCodeRule,
    DuplicateRule,
    LayerRule,
    NamingRule,
)
from aedile.infrastructure.cache import ScanCache
from aedile.shared.config import Config
from aedile.shared.logging import get_logger

logger = get_logger("aedile.core.scanner")


class Scanner:
    def __init__(self, config: Config, cache: ScanCache | None = None) -> None:
        self.config = config
        self.cache = cache
        self.parser = PythonParser()  # Python default parser

    def _should_exclude(self, filepath: str, project_root: str) -> bool:
        # Match against exclusion patterns in config
        norm_path = os.path.relpath(filepath, project_root).replace(os.sep, "/")

        for pattern in self.config.exclude:
            if fnmatch.fnmatch(norm_path, pattern) or fnmatch.fnmatch(os.path.basename(filepath), pattern):
                return True
        return False

    def scan_project(self, project_root: str) -> tuple[list[SourceFile], ArchitectureGraph]:
        """Scans the source directories, parsing modified files and leveraging the cache."""
        source_files: list[SourceFile] = []
        graph = ArchitectureGraph()

        logger.debug(f"Scanning project root: {project_root}")
        start_time = time.time()

        # Step 1: Discover all target files
        target_files: list[str] = []
        for src_dir in self.config.src_dirs:
            full_src_path = os.path.abspath(os.path.join(project_root, src_dir) if not os.path.isabs(src_dir) else src_dir)
            if not os.path.exists(full_src_path):
                logger.warning(f"Source directory not found: {full_src_path}")
                continue

            for root, _, files in os.walk(full_src_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    if file.endswith(".py") and not self._should_exclude(filepath, project_root):
                        target_files.append(filepath)

        logger.debug(f"Discovered {len(target_files)} target source files.")

        # Step 2: Parse discovered files (via Cache or Parser)
        for filepath in target_files:
            try:
                # Compute hash of current file
                with open(filepath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()

                sf = None
                if self.cache:
                    sf = self.cache.get(filepath, file_hash)

                if sf is None:
                    # Parse fresh
                    sf = self.parser.parse(filepath, project_root, self.config.src_dirs)
                    if self.cache:
                        self.cache.set(filepath, sf)

                source_files.append(sf)
            except Exception as e:
                logger.error(f"Error scanning file {filepath}: {e}")

        # Save cache state after batch parse
        if self.cache:
            self.cache.save()

        # Step 3: Map modules to paths and build Dependency Graph
        # We first build a set of all internal modules to filter external imports
        internal_modules: set[str] = set()
        module_to_file_map = {}
        for sf in source_files:
            root = os_path_root(sf.filepath, sf.relative_path)
            module_name = compute_module_name(sf.filepath, root, self.config.src_dirs)
            internal_modules.add(module_name)
            module_to_file_map[module_name] = sf.filepath
            graph.add_node(module_name, sf.filepath)

        # Draw dependency edges in the graph
        for sf in source_files:
            root = os_path_root(sf.filepath, sf.relative_path)
            source_module = compute_module_name(sf.filepath, root, self.config.src_dirs)

            for imp in sf.imports:
                # Check if imported module is internal.
                # It matches if imp.module is an exact match OR a sub-module of an internal module (e.g. package.file)
                target_module = None
                if imp.module in internal_modules:
                    target_module = imp.module
                else:
                    # Check parent packages if it's a deep sub-import
                    parts = imp.module.split(".")
                    for i in range(len(parts), 0, -1):
                        parent_pkg = ".".join(parts[:i])
                        if parent_pkg in internal_modules:
                            target_module = parent_pkg
                            break

                if target_module and target_module != source_module:
                    graph.add_edge(source_module, target_module)

        logger.debug(f"Scan finished in {time.time() - start_time:.3f} seconds.")
        return source_files, graph

    def run_rules(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        """Runs all enabled rule checkers against the graph and parsed files."""
        violations: list[Violation] = []

        # Instantiate and run rules
        rules = [
            CycleRule(self.config),
            LayerRule(self.config),
            BoundaryRule(self.config),
            NamingRule(self.config),
            DeadCodeRule(self.config),
            DuplicateRule(self.config),
        ]

        for rule in rules:
            try:
                rule_violations = rule.evaluate(files, graph)
                violations.extend(rule_violations)
            except Exception as e:
                logger.error(f"Rule '{rule.name}' failed to run: {e}")

        return violations

    def generate_report(
        self, files: list[SourceFile], graph: ArchitectureGraph, violations: list[Violation], scan_duration: float
    ) -> Report:
        """Calculates project metrics and builds the final Report object."""
        total_loc = 0
        for sf in files:
            if os.path.exists(sf.filepath):
                try:
                    with open(sf.filepath, encoding="utf-8", errors="replace") as f:
                        total_loc += len(f.readlines())
                except OSError:
                    pass

        # Calculate counts per rule
        cycle_count = sum(1 for v in violations if v.rule_name == "cycle_detection")
        layer_count = sum(1 for v in violations if v.rule_name == "layer_violations")
        dead_count = sum(1 for v in violations if v.rule_name == "dead_code_detection")
        duplicate_count = sum(1 for v in violations if v.rule_name == "duplicate_architecture")

        # Calculate weighted Architecture Risk Score (0.0 to 100.0)
        # Severity weights: Error = 5, Warning = 1
        total_weight = 0
        for v in violations:
            total_weight += 5 if v.severity == "error" else 1

        # Normalize score over size of project (lines of code / modules)
        # E.g. risk = min(100.0, (total_weight * 50) / (len(files) + 1))
        # This gives a nice scaled score that represents structural health
        risk_score = 0.0
        if files:
            risk_score = min(100.0, (total_weight * 10.0) / len(files))

        metrics = ProjectMetrics(
            total_files=len(files),
            total_loc=total_loc,
            total_violations=len(violations),
            risk_score=round(risk_score, 1),
            dependency_cycles=cycle_count,
            layer_violations=layer_count,
            dead_symbols=dead_count,
            duplicate_groups=duplicate_count,
        )

        return Report(
            project_name=self.config.project_name,
            violations=violations,
            metrics=metrics,
            generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            scan_time_seconds=round(scan_duration, 3),
        )
