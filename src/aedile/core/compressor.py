"""Zero-dependency CLI & tool output compressor inspired by rtk-ai/rtk.

Reduces LLM token consumption by 60-90% on noisy command outputs (pytest,
git diff, ruff, mypy, generic logs) while preserving failure diagnostics
and saving full raw output to `.aedile/recall/<hash>.log` for recovery.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from aedile.infrastructure.telemetry import TelemetryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

CAP_ERRORS = 20
CAP_WARNINGS = 10
CAP_LIST = 20
MIN_FAILURE_BYTES = 512
MAX_TRACEBACK_LINES = 3
MAX_ERROR_LINES = 4
PASSTHROUGH_MAX_CHARS = 2000

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_PYTEST_SUMMARY_RE = re.compile(
    r"^(?:=+\s*)?\d+\s+[^,\r\n=]+(?:,\s*\d+\s+[^,\r\n=]+)*\s+in\s+\d+(?:\.\d+)?(?:s| seconds).*$"
)
_RUFF_MYPY_LINE_RE = re.compile(r"^(.+?:\d+(?::\d+)?:\s*(?:error|warning|note|[A-Z]\d+).*)$")
_DIAG_SUMMARY_RE = re.compile(
    r"^(?:Found\s+\d+\s+error|Success:\s+no\s+issues|All\s+checks\s+passed|\[\*\]\s+).*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CompressionResult:
    """Result of compressing a CLI or tool output."""

    compressed: str
    raw_bytes: int
    compressed_bytes: int
    raw_tokens: int
    compressed_tokens: int
    tokens_saved: int
    savings_pct: float
    recall_id: str | None
    filter_used: str


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    return _ANSI_RE.sub("", text)


def estimate_tokens(text: str) -> int:
    """Estimate LLM tokens deterministically using the standard bytes // 4 heuristic."""
    if not text:
        return 0
    return max(1, len(text.encode("utf-8", errors="replace")) // 4)


def never_worse(raw: str, filtered: str) -> str:
    """Guarantee compressed output never exceeds raw token count (RTK guard invariant)."""
    if estimate_tokens(filtered) > estimate_tokens(raw):
        return strip_ansi(raw).strip()
    return filtered


def compress_pytest(raw: str, exit_code: int = 0) -> str:
    """Compress pytest output to failure summaries and the final result line."""
    clean = strip_ansi(raw).replace("\r\n", "\n")
    lines = clean.splitlines()

    failure_blocks: list[str] = []
    summary_lines: list[str] = []
    in_failures = False
    current_header: str | None = None
    current_trace: list[str] = []
    current_errors: list[str] = []

    def _flush_failure() -> None:
        if current_header is None:
            return
        block = [current_header]
        if current_trace:
            block.extend(current_trace[-MAX_TRACEBACK_LINES:])
        if current_errors:
            block.extend(current_errors[:MAX_ERROR_LINES])
        failure_blocks.append("\n".join(block))

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("=") and "FAILURES" in stripped:
            in_failures = True
            continue
        if stripped.startswith("=") and (
            "short test summary info" in stripped.lower() or "warnings summary" in stripped.lower()
        ):
            _flush_failure()
            current_header = None
            current_trace = []
            current_errors = []
            in_failures = False
            continue
        if _PYTEST_SUMMARY_RE.match(stripped):
            _flush_failure()
            current_header = None
            current_trace = []
            current_errors = []
            in_failures = False
            summary_lines.append(stripped.strip("= "))
            continue
        if in_failures:
            if stripped.startswith("_") and stripped.endswith("_") and len(stripped) > 4:
                _flush_failure()
                current_header = stripped.strip("_ ")
                current_trace = []
                current_errors = []
            elif stripped.startswith("E   "):
                current_errors.append(stripped)
            elif stripped and not stripped.startswith("-"):
                current_trace.append(line.rstrip())
        elif stripped.startswith(("FAILED ", "ERROR ")):
            summary_lines.append(stripped)

    _flush_failure()

    if not failure_blocks and not summary_lines:
        if exit_code != 0:
            trimmed = clean.strip()
            if len(trimmed) > PASSTHROUGH_MAX_CHARS:
                return trimmed[:PASSTHROUGH_MAX_CHARS] + "\n... [truncated crash output]"
            return trimmed
        return compress_generic(clean, max_lines=15)

    out_parts: list[str] = []
    if failure_blocks:
        shown = failure_blocks[:CAP_ERRORS]
        out_parts.extend(shown)
        if len(failure_blocks) > CAP_ERRORS:
            out_parts.append(f"... [+{len(failure_blocks) - CAP_ERRORS} more failures]")
    if summary_lines:
        out_parts.extend(summary_lines[-5:])
    return "\n".join(out_parts)


def compress_git_diff(raw: str) -> str:
    """Compress git diff output by removing unchanged context lines and capping hunks."""
    clean = strip_ansi(raw).replace("\r\n", "\n")
    out: list[str] = []
    hidden = 0
    per_file_lines = 0
    max_per_file = 30

    for line in clean.splitlines():
        if line.startswith(("diff --git ", "--- ", "+++ ", "@@ ")):
            if line.startswith("diff --git "):
                per_file_lines = 0
            out.append(line)
        elif line.startswith(("+", "-")):
            if per_file_lines < max_per_file:
                out.append(line)
                per_file_lines += 1
            else:
                hidden += 1
        # Unchanged context lines (" ...") are dropped to save tokens.

    if hidden > 0:
        out.append(f"... [+{hidden} changed lines omitted]")
    if not out:
        return compress_generic(clean, max_lines=20)
    return "\n".join(out)


def compress_ruff_mypy(raw: str) -> str:
    """Compress ruff/mypy diagnostics to unique errors/warnings capped at CAP_ERRORS."""
    clean = strip_ansi(raw).replace("\r\n", "\n")
    errors: list[str] = []
    summaries: list[str] = []

    for line in clean.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _DIAG_SUMMARY_RE.match(stripped):
            summaries.append(stripped)
        elif _RUFF_MYPY_LINE_RE.match(stripped):
            errors.append(stripped)

    if not errors and not summaries:
        return compress_generic(clean, max_lines=25)

    out = errors[:CAP_ERRORS]
    if len(errors) > CAP_ERRORS:
        out.append(f"... [+{len(errors) - CAP_ERRORS} more diagnostics]")
    out.extend(summaries[-3:])
    return "\n".join(out)


def compress_generic(raw: str, max_lines: int = 40) -> str:
    """Deduplicate consecutive identical lines and bound total lines."""
    clean = strip_ansi(raw).replace("\r\n", "\n")
    deduped: list[str] = []
    prev: str | None = None
    repeat = 0

    for line in clean.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue
        if stripped == prev:
            repeat += 1
            continue
        if prev is not None and repeat > 0:
            deduped[-1] = f"{deduped[-1]} (x{repeat + 1})"
        deduped.append(stripped)
        prev = stripped
        repeat = 0

    if prev is not None and repeat > 0:
        deduped[-1] = f"{deduped[-1]} (x{repeat + 1})"

    if len(deduped) <= max_lines:
        return "\n".join(deduped)

    head_count = max_lines // 2
    tail_count = max_lines - head_count
    hidden = len(deduped) - max_lines
    return "\n".join(
        [*deduped[:head_count], f"... [+{hidden} lines omitted]", *deduped[-tail_count:]]
    )


def _select_filter(command: str, raw: str) -> tuple[str, str]:
    cmd_lower = command.lower()
    if "pytest" in cmd_lower or "=== test session starts ===" in raw:
        return "pytest", "pytest"
    if "git diff" in cmd_lower or raw.lstrip().startswith("diff --git "):
        return "git_diff", "git_diff"
    if "ruff" in cmd_lower or "mypy" in cmd_lower:
        return "ruff_mypy", "ruff_mypy"
    return "generic", "generic"


def _save_recall(raw: str, project_root: str) -> str:
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
    recall_dir = Path(project_root) / ".aedile" / "recall"
    recall_dir.mkdir(parents=True, exist_ok=True)
    recall_file = recall_dir / f"{digest}.log"
    recall_file.write_text(raw, encoding="utf-8")
    return digest


def recall_output(hash_prefix: str, project_root: str = ".") -> str | None:
    """Retrieve stored raw command output by hash prefix from `.aedile/recall/`."""
    recall_dir = Path(project_root) / ".aedile" / "recall"
    if not recall_dir.is_dir():
        return None
    for path in sorted(recall_dir.glob("*.log")):
        if path.stem.startswith(hash_prefix):
            return path.read_text(encoding="utf-8", errors="replace")
    return None


def compress_output(
    raw: str,
    command: str = "",
    exit_code: int = 0,
    project_root: str | None = None,
    record_telemetry: bool = True,
) -> CompressionResult:
    """Compress raw CLI/tool output, save recall log on large failures, and track savings."""
    cmd_tokens = command.split()
    is_help_or_version = any(tok in {"--help", "-h", "--version", "-V"} for tok in cmd_tokens)

    if is_help_or_version:
        filter_name = "passthrough"
        compressed = strip_ansi(raw).strip()
    else:
        filter_name, _ = _select_filter(command, raw)
        if filter_name == "pytest":
            compressed = compress_pytest(raw, exit_code=exit_code)
        elif filter_name == "git_diff":
            compressed = compress_git_diff(raw)
        elif filter_name == "ruff_mypy":
            compressed = compress_ruff_mypy(raw)
        else:
            compressed = compress_generic(raw)

    raw_bytes = len(raw.encode("utf-8", errors="replace"))
    recall_id: str | None = None

    # Save full output for recovery when output is compressed on non-zero exit or large loss.
    if (
        not is_help_or_version
        and project_root is not None
        and raw_bytes >= MIN_FAILURE_BYTES
        and len(compressed.encode("utf-8", errors="replace")) < raw_bytes
        and (exit_code != 0 or "[+" in compressed)
    ):
        recall_id = _save_recall(raw, project_root)
        compressed = f"{compressed}\n[full output: aedile recall {recall_id}]"

    compressed = never_worse(raw, compressed)
    compressed_bytes = len(compressed.encode("utf-8", errors="replace"))

    raw_tokens = estimate_tokens(raw)
    compressed_tokens = estimate_tokens(compressed)
    tokens_saved = max(0, raw_tokens - compressed_tokens)
    savings_pct = round((tokens_saved / raw_tokens) * 100.0, 1) if raw_tokens > 0 else 0.0

    if record_telemetry and project_root is not None and tokens_saved > 0:
        TelemetryStore(project_root).record(
            event="compress_output",
            estimated_tokens_saved=tokens_saved,
        )

    return CompressionResult(
        compressed=compressed,
        raw_bytes=raw_bytes,
        compressed_bytes=compressed_bytes,
        raw_tokens=raw_tokens,
        compressed_tokens=compressed_tokens,
        tokens_saved=tokens_saved,
        savings_pct=savings_pct,
        recall_id=recall_id,
        filter_used=filter_name,
    )


def run_and_compress(
    argv: Sequence[str],
    project_root: str = ".",
    record_telemetry: bool = True,
) -> tuple[int, CompressionResult]:
    """Execute a subprocess command, compress its combined output, and track token savings."""
    proc = subprocess.run(
        list(argv),
        cwd=os.path.abspath(project_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    result = compress_output(
        raw=combined,
        command=" ".join(argv),
        exit_code=proc.returncode,
        project_root=project_root,
        record_telemetry=record_telemetry,
    )
    return proc.returncode, result
