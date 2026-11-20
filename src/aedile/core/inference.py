import os

from aedile.core.models import SourceFile
from aedile.shared.config import Config

# Canonical Clean/Layered Architecture tiers from top (presentation) to bottom (shared)
DEFAULT_LAYER_HEURISTICS: list[tuple[str, tuple[str, ...]]] = [
    ("presentation", ("cli", "ui", "api", "routes", "web", "views", "handlers", "mcp")),
    ("application", ("application", "services", "use_cases", "scanner", "workflows")),
    ("infrastructure", ("infrastructure", "infra", "db", "storage", "cache", "adapters")),
    ("domain", ("domain", "core", "models", "entities", "rules", "parser", "graph")),
    ("shared", ("shared", "common", "utils", "helpers", "lib", "types", "errors")),
]


def infer_layers(files: list[SourceFile], config: Config) -> Config:
    """Infers layer_order and layer_mappings from discovered source paths when unconfigured.

    Mutates nothing on disk and returns a shallow-updated Config if layers were empty.
    """
    if config.layer_order and config.layer_mappings:
        return config

    discovered_dirs: set[str] = set()
    for sf in files:
        parts = sf.relative_path.replace("\\", "/").split("/")
        for part in parts[:-1]:
            discovered_dirs.add(part.lower())

    inferred_order: list[str] = []
    inferred_mappings: dict[str, list[str]] = {}

    for layer_name, keywords in DEFAULT_LAYER_HEURISTICS:
        matched_patterns: list[str] = []
        for kw in keywords:
            if kw in discovered_dirs or any(
                f"/{kw}/" in f"/{sf.relative_path.lower()}" for sf in files
            ):
                matched_patterns.append(f"**/{kw}/**")
        if matched_patterns:
            inferred_order.append(layer_name)
            inferred_mappings[layer_name] = sorted(set(matched_patterns))

    if inferred_order:
        config.layer_order = inferred_order
        config.layer_mappings = inferred_mappings

    return config


def detect_src_dirs(project_root: str) -> list[str]:
    """Detects likely source directories for zero-config `aedile init` / `aedile check`."""
    candidates = ["src", "app", "lib", "pkg"]
    found = [c for c in candidates if os.path.isdir(os.path.join(project_root, c))]
    return found or ["."]
