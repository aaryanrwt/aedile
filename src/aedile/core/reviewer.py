import os
import subprocess
from dataclasses import dataclass

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.parser import compute_module_name, os_path_root
from aedile.shared.config import Config


@dataclass
class ReviewFinding:
    severity: str  # "must_fix", "should_fix", "nice_to_have"
    title: str
    location: str
    what_this_is: str
    problem: str
    fix: str
    if_skipped: str


def _git_changed_files(project_root: str, base_ref: str = "HEAD") -> list[str]:
    """Returns relative paths of modified/untracked files using git."""
    if not base_ref or base_ref.startswith("-") or any(c.isspace() or c == "\x00" for c in base_ref):
        return []
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", base_ref, "--"],
            cwd=project_root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        changed = [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]
        if changed:
            return changed
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return [
            line[3:].strip().replace("\\", "/")
            for line in status.splitlines()
            if len(line) > 3
        ]
    except Exception:
        return []


def review_changes(
    project_root: str,
    files: list[SourceFile],
    graph: ArchitectureGraph,
    violations: list[Violation],
    config: Config,
    changed_paths: list[str] | None = None,
    base_ref: str = "HEAD",
) -> list[ReviewFinding]:
    """Performs caller-aware, blast-radius architectural review on changed files."""
    targets = changed_paths if changed_paths is not None else _git_changed_files(project_root, base_ref)
    if not targets:
        # Fallback: review highest-fan-in modules in the repo
        targets = [sf.relative_path for sf in files[:10]]

    target_set = {t.replace("\\", "/") for t in targets}
    findings: list[ReviewFinding] = []

    # 1. Architectural violations touching changed files
    for v in violations:
        if v.relative_path in target_set:
            sev = "must_fix" if v.severity == "error" else "should_fix"
            findings.append(
                ReviewFinding(
                    severity=sev,
                    title=f"{v.rule_name} violation",
                    location=f"{v.relative_path}:L{v.line}",
                    what_this_is=f"Module `{v.relative_path}` triggers rule `{v.rule_name}`.",
                    problem=v.message,
                    fix="Resolve the dependency direction or extract shared abstractions.",
                    if_skipped="Architectural coupling degrades and future refactors break callers.",
                )
            )

    # 2. Blast-radius & high-coupling warnings for changed modules
    for sf in files:
        if sf.relative_path not in target_set:
            continue
        mod = compute_module_name(
            sf.filepath, os_path_root(sf.filepath, sf.relative_path), config.src_dirs
        )
        blast = graph.get_blast_radius(mod)
        metrics = graph.get_coupling_metrics(mod)
        if len(blast) >= 3:
            sample = ", ".join(sorted(blast)[:4])
            findings.append(
                ReviewFinding(
                    severity="should_fix",
                    title=f"High blast radius on `{mod}` ({len(blast)} transitive dependents)",
                    location=sf.relative_path,
                    what_this_is=f"`{mod}` has fan-in={metrics['fan_in']}, instability={metrics['instability']}.",
                    problem=f"Edits here transitively affect {len(blast)} modules (e.g. {sample}).",
                    fix="Verify all callers and keep public signatures backward-compatible.",
                    if_skipped="Downstream callers outside this diff may fail at runtime.",
                )
            )

    # 3. Missing test check for non-trivial changed source files
    test_names = {
        os.path.basename(sf.relative_path).lower()
        for sf in files
        if "test" in sf.relative_path.lower()
    }
    for rel in sorted(target_set):
        if rel.endswith(".py") and not rel.startswith("tests/") and "test_" not in rel:
            stem = os.path.splitext(os.path.basename(rel))[0]
            has_test = any(stem in tn for tn in test_names)
            if not has_test and os.path.exists(os.path.join(project_root, rel)):
                findings.append(
                    ReviewFinding(
                        severity="nice_to_have",
                        title=f"No matching test module detected for `{stem}.py`",
                        location=rel,
                        what_this_is=f"Source module `{rel}` was modified.",
                        problem=f"No test file matching `*{stem}*` was found in scanned sources.",
                        fix=f"Add a focused unit test covering core branches in `{rel}`.",
                        if_skipped="Regressions in this module will not be caught automatically.",
                    )
                )

    return findings


def format_review(findings: list[ReviewFinding]) -> str:
    if not findings:
        return "Looks good. Ship.\nChecked architectural rules, blast radius, and test coverage."
    groups = [("must_fix", "Must fix"), ("should_fix", "Should fix"), ("nice_to_have", "Nice to have")]
    lines = ["### Aedile Blast-Radius Review"]
    idx = 1
    for key, label in groups:
        items = [f for f in findings if f.severity == key]
        if not items:
            continue
        lines.append(f"\n#### {label}")
        for f in items:
            lines.append(f"{idx}. **{f.title}** (`{f.location}`)")
            lines.append(f"   - **What this is:** {f.what_this_is}")
            lines.append(f"   - **Problem:** {f.problem}")
            lines.append(f"   - **Fix:** {f.fix}")
            lines.append(f"   - **If we skip it:** {f.if_skipped}")
            idx += 1
    return "\n".join(lines)
