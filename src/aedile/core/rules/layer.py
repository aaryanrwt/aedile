import fnmatch
import os

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.rules.base import BaseRule


class LayerRule(BaseRule):
    @property
    def name(self) -> str:
        return "layer_violations"

    def _get_layer_for_file(self, rel_path: str) -> str | None:
        """Returns the layer name that matches the given relative file path, if any."""
        norm_path = rel_path.replace(os.sep, "/")

        # Check matching layers based on order to maintain deterministic priority
        for layer in self.config.layer_order:
            patterns = self.config.layer_mappings.get(layer, [])
            for pattern in patterns:
                # Match full path or pattern wildcard
                if fnmatch.fnmatch(norm_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                    return layer
        return None

    def _get_layer_for_module(self, module_name: str, files: list[SourceFile]) -> str | None:
        """Infers the layer of an imported module by matching it with files in our codebase."""
        # Find the source file corresponding to this module name
        from aedile.core.parser import compute_module_name, os_path_root

        for sf in files:
            root = os_path_root(sf.filepath, sf.relative_path)
            sf_module = compute_module_name(sf.filepath, root, self.config.src_dirs)
            if sf_module == module_name or sf_module.startswith(module_name + "."):
                return self._get_layer_for_file(sf.relative_path)

        # If it doesn't match a local module, check mapping patterns directly against module path
        # by converting module dots to slashes (e.g. 'aedile.shared.config' -> 'aedile/shared/config')
        dummy_rel_path = module_name.replace(".", "/") + ".py"
        return self._get_layer_for_file(dummy_rel_path)

    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        violations: list[Violation] = []
        if not self.config.layer_violations or not self.config.layer_order:
            return violations

        # Order index map: layer -> index
        layer_indices = {layer: idx for idx, layer in enumerate(self.config.layer_order)}

        for sf in files:
            source_layer = self._get_layer_for_file(sf.relative_path)
            if not source_layer:
                continue  # Skip un-layered files

            source_idx = layer_indices[source_layer]

            for imp in sf.imports:
                target_layer = self._get_layer_for_module(imp.module, files)
                if not target_layer or target_layer == source_layer:
                    continue  # Target is not layered, or is in the same layer

                target_idx = layer_indices[target_layer]

                # Violation: dependencies cannot flow upwards (i.e. target_idx < source_idx)
                if target_idx < source_idx:
                    violations.append(
                        Violation(
                            rule_name=self.name,
                            filepath=sf.filepath,
                            relative_path=sf.relative_path,
                            line=imp.line,
                            message=(
                                f"Layer violation: Layer '{source_layer}' is not allowed to import "
                                f"from layer '{target_layer}' (strict downward flow enforced: "
                                f"{' -> '.join(self.config.layer_order)}). "
                                f"Source '{sf.relative_path}' imports '{imp.module}'."
                            ),
                            offending_symbol=imp.module,
                            confidence=1.0,
                            severity="error",
                        )
                    )

        return violations
