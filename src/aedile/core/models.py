from dataclasses import dataclass, field
from typing import Any


@dataclass
class Import:
    module: str               # The fully-qualified module imported (e.g. 'aedile.core.scanner')
    names: list[str]          # Specific symbols imported (e.g. ['Scanner']) or empty for full module imports
    line: int                 # Line number of the import statement
    alias: str | None = None # Alias if imported as (e.g. 'import x as y')
    is_relative: bool = False # Whether it's a relative import


@dataclass
class Symbol:
    name: str                 # Symbol name (e.g. 'Scanner')
    kind: str                 # 'class', 'function', 'variable', 'method'
    line: int                 # Starting line number
    end_line: int             # Ending line number
    docstring: str | None = None
    is_private: bool = False  # Derived from name prefix (e.g. starts with '_')


@dataclass
class SourceFile:
    filepath: str             # Absolute file path
    relative_path: str        # Path relative to project root
    file_hash: str            # SHA256 of contents (for incremental scanning)
    file_size: int            # Size in bytes
    language: str             # 'python', 'javascript', etc.
    imports: list[Import] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)


@dataclass
class Violation:
    rule_name: str            # Unique name of the violated rule
    filepath: str             # File where the violation occurred
    relative_path: str        # Relative file path
    line: int                 # Line number of the violation
    message: str              # Description of the violation
    offending_symbol: str | None = None
    confidence: float = 1.0   # Confidence score (0.0 to 1.0)
    severity: str = "error"   # "error" or "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "filepath": self.filepath,
            "relative_path": self.relative_path,
            "line": self.line,
            "message": self.message,
            "offending_symbol": self.offending_symbol,
            "confidence": self.confidence,
            "severity": self.severity,
        }


@dataclass
class DuplicateGroup:
    similarity: float
    files: list[str]          # Paths to similar files
    common_patterns: list[str]


@dataclass
class ProjectMetrics:
    total_files: int = 0
    total_loc: int = 0
    total_violations: int = 0
    risk_score: float = 0.0   # Weighted architecture risk score (0 to 100)
    dependency_cycles: int = 0
    layer_violations: int = 0
    dead_symbols: int = 0
    duplicate_groups: int = 0


@dataclass
class Report:
    project_name: str
    violations: list[Violation]
    metrics: ProjectMetrics
    generated_at: str
    scan_time_seconds: float
