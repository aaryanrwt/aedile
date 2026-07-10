import os
import re
import tomllib
from typing import Any

from aedile.shared.errors import ConfigError


class NamingPattern:
    def __init__(
        self,
        path_pattern: str,
        class_pattern: str | None = None,
        function_pattern: str | None = None,
        file_pattern: str | None = None,
    ):
        self.path_pattern = path_pattern
        self.class_pattern = class_pattern
        self.function_pattern = function_pattern
        self.file_pattern = file_pattern

        # Precompile patterns to validate regex
        self._class_re = re.compile(class_pattern) if class_pattern else None
        self._func_re = re.compile(function_pattern) if function_pattern else None
        self._file_re = re.compile(file_pattern) if file_pattern else None

    def matches_class(self, name: str) -> bool:
        return self._class_re.match(name) is not None if self._class_re else True

    def matches_function(self, name: str) -> bool:
        return self._func_re.match(name) is not None if self._func_re else True

    def matches_file(self, name: str) -> bool:
        return self._file_re.match(name) is not None if self._file_re else True


class Config:
    def __init__(self) -> None:
        # Project settings
        self.project_name: str = "Aedile"
        self.src_dirs: list[str] = ["src"]
        self.exclude: list[str] = []
        self.languages: list[str] = ["python"]
        self.confidence_threshold: float = 0.7

        # Layers
        self.layer_order: list[str] = []
        self.layer_mappings: dict[str, list[str]] = {}

        # Rules activation
        self.cycle_detection: bool = True
        self.layer_violations: bool = True
        self.module_boundaries: bool = True
        self.naming_conventions: bool = True
        self.dead_code_detection: bool = True
        self.duplicate_architecture: bool = True

        # Rule parameters
        self.naming_patterns: list[NamingPattern] = []
        self.private_prefixes: list[str] = ["_"]
        self.strict_boundaries: bool = True
        self.duplicate_similarity_threshold: float = 0.85
        self.duplicate_min_file_size: int = 100

    @classmethod
    def default(cls) -> "Config":
        return cls()

    @classmethod
    def load_from_file(cls, filepath: str) -> "Config":
        if not os.path.exists(filepath):
            raise ConfigError(f"Configuration file not found: {filepath}")

        try:
            with open(filepath, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            raise ConfigError(f"Failed to parse TOML configuration: {e}")

        config = cls()
        config._parse(data)
        config.validate()
        return config

    def _parse(self, data: dict[str, Any]) -> None:
        # Parse project
        project = data.get("project", {})
        if not isinstance(project, dict):
            raise ConfigError("Section [project] must be a table")
        self.project_name = project.get("name", self.project_name)
        self.src_dirs = project.get("src_dirs", self.src_dirs)
        self.exclude = project.get("exclude", self.exclude)
        self.languages = project.get("languages", self.languages)
        self.confidence_threshold = project.get("confidence_threshold", self.confidence_threshold)

        # Parse layers
        layers = data.get("layers", {})
        if not isinstance(layers, dict):
            raise ConfigError("Section [layers] must be a table")
        self.layer_order = layers.get("order", self.layer_order)
        self.layer_mappings = layers.get("mappings", self.layer_mappings)

        # Parse rules
        rules = data.get("rules", {})
        if not isinstance(rules, dict):
            raise ConfigError("Section [rules] must be a table")
        self.cycle_detection = rules.get("cycle_detection", self.cycle_detection)
        self.layer_violations = rules.get("layer_violations", self.layer_violations)
        self.module_boundaries = rules.get("module_boundaries", self.module_boundaries)
        self.naming_conventions = rules.get("naming_conventions", self.naming_conventions)
        self.dead_code_detection = rules.get("dead_code_detection", self.dead_code_detection)
        self.duplicate_architecture = rules.get(
            "duplicate_architecture", self.duplicate_architecture
        )

        # Parse naming patterns
        naming = rules.get("naming", {})
        if isinstance(naming, dict):
            patterns = naming.get("patterns", [])
            if isinstance(patterns, list):
                for p in patterns:
                    if not isinstance(p, dict) or "path_pattern" not in p:
                        raise ConfigError(
                            "Naming pattern must be a table containing 'path_pattern'"
                        )
                    try:
                        self.naming_patterns.append(
                            NamingPattern(
                                path_pattern=p["path_pattern"],
                                class_pattern=p.get("class_pattern"),
                                function_pattern=p.get("function_pattern"),
                                file_pattern=p.get("file_pattern"),
                            )
                        )
                    except re.error as e:
                        raise ConfigError(f"Invalid regex pattern in naming rule: {e}")

        # Parse boundaries
        boundaries = rules.get("boundaries", {})
        if isinstance(boundaries, dict):
            self.private_prefixes = boundaries.get("private_prefixes", self.private_prefixes)
            self.strict_boundaries = boundaries.get("strict_boundaries", self.strict_boundaries)

        # Parse duplicates
        duplicates = rules.get("duplicates", {})
        if isinstance(duplicates, dict):
            self.duplicate_similarity_threshold = duplicates.get(
                "similarity_threshold", self.duplicate_similarity_threshold
            )
            self.duplicate_min_file_size = duplicates.get(
                "min_file_size_bytes", self.duplicate_min_file_size
            )

    def validate(self) -> None:
        # Validate project
        if not isinstance(self.project_name, str) or not self.project_name:
            raise ConfigError("project.name must be a non-empty string")
        if not isinstance(self.src_dirs, list) or not all(
            isinstance(d, str) for d in self.src_dirs
        ):
            raise ConfigError("project.src_dirs must be a list of strings")
        if not isinstance(self.exclude, list) or not all(isinstance(e, str) for e in self.exclude):
            raise ConfigError("project.exclude must be a list of strings")
        if not isinstance(self.languages, list) or not all(
            isinstance(l, str) for l in self.languages
        ):
            raise ConfigError("project.languages must be a list of strings")
        if not isinstance(self.confidence_threshold, (int, float)) or not (
            0.0 <= self.confidence_threshold <= 1.0
        ):
            raise ConfigError("project.confidence_threshold must be a float between 0.0 and 1.0")

        # Validate layers
        if not isinstance(self.layer_order, list) or not all(
            isinstance(o, str) for o in self.layer_order
        ):
            raise ConfigError("layers.order must be a list of strings")
        if not isinstance(self.layer_mappings, dict) or not all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(val, str) for val in v)
            for k, v in self.layer_mappings.items()
        ):
            raise ConfigError("layers.mappings must be a dictionary of string to list of strings")

        # Validate layer order matches mappings
        for layer in self.layer_order:
            if layer not in self.layer_mappings:
                raise ConfigError(f"Layer '{layer}' declared in order is missing from mappings")

        # Validate rule parameters
        if not isinstance(self.private_prefixes, list) or not all(
            isinstance(p, str) for p in self.private_prefixes
        ):
            raise ConfigError("rules.boundaries.private_prefixes must be a list of strings")
        if not isinstance(self.duplicate_similarity_threshold, (int, float)) or not (
            0.0 <= self.duplicate_similarity_threshold <= 1.0
        ):
            raise ConfigError(
                "rules.duplicates.similarity_threshold must be a float between 0.0 and 1.0"
            )
        if not isinstance(self.duplicate_min_file_size, int) or self.duplicate_min_file_size < 0:
            raise ConfigError("rules.duplicates.min_file_size_bytes must be a non-negative integer")
