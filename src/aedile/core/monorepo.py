import os
import tomllib

from aedile.core.models import SourceFile, Violation


def discover_workspace_packages(project_root: str) -> dict[str, str]:
    """Discovers sub-packages in uv / pyproject.toml / pnpm workspaces."""
    packages: dict[str, str] = {}
    abs_root = os.path.abspath(project_root)

    pyproject = os.path.join(abs_root, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            members = (
                data.get("tool", {})
                .get("uv", {})
                .get("workspace", {})
                .get("members", [])
            )
            for m in members:
                base = str(m).rstrip("/*")
                cand = os.path.join(abs_root, base)
                if os.path.isdir(cand):
                    for entry in os.listdir(cand):
                        sub = os.path.join(cand, entry)
                        if os.path.isdir(sub) and os.path.exists(
                            os.path.join(sub, "pyproject.toml")
                        ):
                            packages[entry] = os.path.relpath(sub, abs_root).replace(os.sep, "/")
        except Exception:
            pass

    if not packages:
        for folder in ("packages", "apps", "services"):
            cand = os.path.join(abs_root, folder)
            if os.path.isdir(cand):
                for entry in sorted(os.listdir(cand)):
                    sub = os.path.join(cand, entry)
                    if os.path.isdir(sub):
                        packages[entry] = f"{folder}/{entry}"

    return packages


def check_cross_package_boundaries(
    files: list[SourceFile],
    packages: dict[str, str],
) -> list[Violation]:
    """Flags imports reaching into another workspace package's private `_` internals."""
    violations: list[Violation] = []
    if not packages:
        return violations

    for sf in files:
        owner_pkg = None
        for pkg_name, pkg_rel in packages.items():
            if sf.relative_path.startswith(pkg_rel + "/"):
                owner_pkg = pkg_name
                break
        if not owner_pkg:
            continue

        for imp in sf.imports:
            parts = imp.module.split(".")
            target_pkg = parts[0] if parts else ""
            if target_pkg in packages and target_pkg != owner_pkg:
                if any(p.startswith("_") for p in parts[1:]):
                    violations.append(
                        Violation(
                            rule_name="monorepo_boundary",
                            filepath=sf.filepath,
                            relative_path=sf.relative_path,
                            line=imp.line,
                            message=(
                                f"Package '{owner_pkg}' imports private internal '{imp.module}' "
                                f"from workspace package '{target_pkg}'."
                            ),
                            offending_symbol=imp.module,
                            confidence=1.0,
                            severity="error",
                        )
                    )
    return violations
