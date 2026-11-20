import hashlib
import json
import os
from typing import Any

from aedile.core.models import Violation


def _fingerprint(v: Violation) -> str:
    """Stable fingerprint for a violation across line-number shifts."""
    raw = f"{v.rule_name}|{v.relative_path}|{v.offending_symbol or ''}|{v.severity}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class BaselineManager:
    """Tracks baselined architectural violations in `.aedile/baseline.json`."""

    def __init__(self, project_root: str, baseline_path: str | None = None) -> None:
        self.project_root = os.path.abspath(project_root)
        self.baseline_path = baseline_path or os.path.join(
            self.project_root, ".aedile", "baseline.json"
        )

    def load(self) -> set[str]:
        if not os.path.exists(self.baseline_path):
            return set()
        try:
            with open(self.baseline_path, encoding="utf-8") as f:
                data = json.load(f)
            return {str(item["fingerprint"]) for item in data.get("violations", [])}
        except Exception:
            return set()

    def save(self, violations: list[Violation]) -> str:
        parent = os.path.dirname(self.baseline_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload: dict[str, Any] = {
            "version": 1,
            "count": len(violations),
            "violations": [
                {
                    "fingerprint": _fingerprint(v),
                    "rule_name": v.rule_name,
                    "relative_path": v.relative_path,
                    "offending_symbol": v.offending_symbol,
                    "severity": v.severity,
                    "message": v.message,
                }
                for v in violations
            ],
        }
        with open(self.baseline_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return self.baseline_path

    def filter_new(self, violations: list[Violation]) -> tuple[list[Violation], int]:
        """Returns `(new_violations, suppressed_count)` against the saved baseline."""
        known = self.load()
        if not known:
            return violations, 0
        new_ones = [v for v in violations if _fingerprint(v) not in known]
        return new_ones, len(violations) - len(new_ones)
