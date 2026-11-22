"""55-test real-world token-savings & pre-write architectural gate benchmark for Aedile."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AEDILE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEDILE_ROOT / "src"))

from aedile.core.compressor import compress_output, estimate_tokens  # noqa: E402
from aedile.mcp.server import AedileMcpServer  # noqa: E402


def _run_cmd(argv: list[str]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(AEDILE_ROOT / "src")
    proc = subprocess.run(
        argv,
        cwd=str(AEDILE_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode, proc.stdout + ("\n" + proc.stderr if proc.stderr else "")


def run_compression_suite() -> list[dict[str, Any]]:
    """30 real CLI/tool output compression tests executed against the live Aedile repo."""
    commands: list[tuple[str, list[str]]] = [
        (
            "pytest: test_mcp",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_mcp.py", "-v"],
        ),
        (
            "pytest: test_v1_1_buffs",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_v1_1_buffs.py", "-v"],
        ),
        (
            "pytest: test_graph",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_graph.py", "-v"],
        ),
        (
            "pytest: test_scanner",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_scanner.py", "-v"],
        ),
        (
            "pytest: test_rules",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_rules.py", "-v"],
        ),
        (
            "pytest: test_cli",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_cli.py", "-v"],
        ),
        (
            "pytest: test_verifier",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_verifier.py", "-v"],
        ),
        (
            "pytest: test_baseline",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_baseline.py", "-v"],
        ),
        (
            "pytest: test_polyglot",
            [sys.executable, "-m", "pytest", "-o", "addopts=", "tests/test_polyglot.py", "-v"],
        ),
        ("pytest: full suite", [sys.executable, "-m", "pytest", "-o", "addopts=", "-v"]),
        ("git: log -n 25", ["git", "log", "-n", "25", "--stat"]),
        ("git: log -n 50 oneline", ["git", "log", "-n", "50", "--oneline"]),
        ("git: diff HEAD~1..HEAD", ["git", "diff", "HEAD~1..HEAD"]),
        ("git: diff HEAD~3..HEAD", ["git", "diff", "HEAD~3..HEAD"]),
        ("git: diff HEAD~5..HEAD", ["git", "diff", "HEAD~5..HEAD"]),
        ("git: show HEAD~1", ["git", "show", "HEAD~1"]),
        ("git: status -v", ["git", "status"]),
        ("git: ls-files", ["git", "ls-files"]),
        ("ruff: check .", [sys.executable, "-m", "ruff", "check", "."]),
        (
            "ruff: check --statistics",
            [sys.executable, "-m", "ruff", "check", "--statistics", "src"],
        ),
        ("mypy: src/", [sys.executable, "-m", "mypy", "src/"]),
        ("aedile: check", [sys.executable, "-m", "aedile", "check"]),
        ("aedile: audit", [sys.executable, "-m", "aedile", "audit"]),
        ("aedile: insights", [sys.executable, "-m", "aedile", "insights"]),
        ("aedile: doctor", [sys.executable, "-m", "aedile", "doctor"]),
        ("aedile: map 2000", [sys.executable, "-m", "aedile", "map", "--budget", "2000"]),
        ("aedile: map 800", [sys.executable, "-m", "aedile", "map", "--budget", "800"]),
        ("aedile: debt", [sys.executable, "-m", "aedile", "debt"]),
        ("aedile: graph mermaid", [sys.executable, "-m", "aedile", "graph", "--format", "mermaid"]),
        ("aedile: graph svg", [sys.executable, "-m", "aedile", "graph", "--format", "svg"]),
    ]

    results: list[dict[str, Any]] = []
    for idx, (label, argv) in enumerate(commands, start=1):
        t0 = time.perf_counter()
        rc, raw = _run_cmd(argv)
        res = compress_output(
            raw=raw,
            command=" ".join(argv),
            exit_code=rc,
            project_root=None,  # keep benchmark isolated from .aedile/
            record_telemetry=False,
        )
        ms = round((time.perf_counter() - t0) * 1000, 1)
        results.append(
            {
                "id": idx,
                "category": "cli_compression",
                "name": label,
                "exit_code": rc,
                "filter": res.filter_used,
                "raw_tokens": res.raw_tokens,
                "compressed_tokens": res.compressed_tokens,
                "tokens_saved": res.tokens_saved,
                "savings_pct": res.savings_pct,
                "elapsed_ms": ms,
            }
        )
    return results


def run_prewrite_suite() -> list[dict[str, Any]]:
    """25 real pre-write architectural gate tests ('why should this code exist?')."""
    server = AedileMcpServer(str(AEDILE_ROOT))
    server.refresh_index()

    # Baseline full-repo context cost if an LLM reads raw src/ instead of querying Aedile
    total_src_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in (AEDILE_ROOT / "src" / "aedile").rglob("*.py")
    )
    full_repo_tokens = estimate_tokens(total_src_text)

    consult_queries = [
        ("consult: Tarjan cycle detection", "find_all_cycles", "Detect circular import cycles"),
        ("consult: BM25 symbol search", "search_symbols", "Search codebase symbols with BM25"),
        ("consult: AST codebase map", "build_codebase_map", "Generate token-budgeted codebase map"),
        ("consult: Telemetry store", "TelemetryStore", "Track token savings and reused symbols"),
        ("consult: SARIF report export", "to_sarif", "Export architectural violations to SARIF"),
        ("consult: cProfile hotspots", "profile_target", "Profile Python script hotspots"),
        (
            "consult: Community detection",
            "detect_communities",
            "Detect module communities in graph",
        ),
        ("consult: Layer inference", "infer_layers", "Infer architectural layers from paths"),
        (
            "consult: Monorepo boundaries",
            "discover_workspace_packages",
            "Check cross-package boundaries",
        ),
        ("consult: Baseline ratchet", "BaselineManager", "Track architectural baseline ratchet"),
        ("consult: Stdlib JSON parser", "parse_json_config", "Parse JSON configuration safely"),
        ("consult: Stdlib SHA-256 hash", "compute_sha256", "Compute SHA-256 hash of string"),
        ("consult: Stdlib HTTP server", "start_http_board", "Serve local HTTP dashboard"),
        ("consult: Output compressor", "compress_output", "Compress pytest and git diff output"),
        ("consult: Debt ledger scan", "scan_debt", "Scan shortcut and aedile-waive tags"),
    ]

    results: list[dict[str, Any]] = []
    idx = 31
    for label, query, intent in consult_queries:
        t0 = time.perf_counter()
        resp = server.handle_consult({"query": query, "intent": intent})
        text = resp["content"][0]["text"]
        resp_tokens = estimate_tokens(text)
        # Savings vs naive full-source context read
        tokens_saved = max(0, full_repo_tokens - resp_tokens)
        pct = round((tokens_saved / full_repo_tokens) * 100.0, 1) if full_repo_tokens > 0 else 0.0
        ms = round((time.perf_counter() - t0) * 1000, 1)
        results.append(
            {
                "id": idx,
                "category": "prewrite_consult",
                "name": label,
                "raw_tokens": full_repo_tokens,
                "compressed_tokens": resp_tokens,
                "tokens_saved": tokens_saved,
                "savings_pct": pct,
                "reuse_hit": (
                    "Existing" in text or "stdlib" in text.lower() or "matches" in text.lower()
                ),
                "elapsed_ms": ms,
            }
        )
        idx += 1

    # 10 pre-edit architectural verification checks
    verify_cases: list[tuple[str, list[dict[str, Any]], bool]] = [
        (
            "verify: valid leaf helper",
            [{"path": "src/aedile/shared/str_util.py", "action": "add", "imports": []}],
            True,
        ),
        (
            "verify: valid core module",
            [
                {
                    "path": "src/aedile/core/metrics_ext.py",
                    "action": "add",
                    "imports": ["aedile.shared.config"],
                }
            ],
            True,
        ),
        (
            "verify: valid cli helper",
            [
                {
                    "path": "src/aedile/cli/fmt_helper.py",
                    "action": "add",
                    "imports": ["aedile.core.models"],
                }
            ],
            True,
        ),
        (
            "verify: valid infra cache",
            [
                {
                    "path": "src/aedile/infrastructure/mem_cache.py",
                    "action": "add",
                    "imports": ["aedile.shared.logging"],
                }
            ],
            True,
        ),
        (
            "verify: valid mcp helper",
            [
                {
                    "path": "src/aedile/mcp/schema_util.py",
                    "action": "add",
                    "imports": ["aedile.core.models"],
                }
            ],
            True,
        ),
        (
            "verify: catch shared->core layer violation",
            [
                {
                    "path": "src/aedile/shared/bad_layer.py",
                    "action": "add",
                    "imports": ["aedile.core.scanner"],
                }
            ],
            False,
        ),
        (
            "verify: catch core->cli layer violation",
            [
                {
                    "path": "src/aedile/core/bad_cli.py",
                    "action": "add",
                    "imports": ["aedile.cli.doctor"],
                }
            ],
            False,
        ),
        (
            "verify: catch core->mcp layer violation",
            [
                {
                    "path": "src/aedile/core/bad_mcp.py",
                    "action": "add",
                    "imports": ["aedile.mcp.server"],
                }
            ],
            False,
        ),
        (
            "verify: catch shared->infra violation",
            [
                {
                    "path": "src/aedile/shared/bad_infra.py",
                    "action": "add",
                    "imports": ["aedile.infrastructure.cache"],
                }
            ],
            False,
        ),
        (
            "verify: catch circular self/core cycle",
            [
                {
                    "path": "src/aedile/core/scanner.py",
                    "action": "modify",
                    "imports": ["aedile.cli.setup"],
                }
            ],
            False,
        ),
    ]

    for label, changes, expected_ok in verify_cases:
        t0 = time.perf_counter()
        resp = server.handle_verify_architecture({"proposed_changes": changes})
        text = resp["content"][0]["text"]
        passed = "PASSED" in text
        resp_tokens = estimate_tokens(text)
        # Comparing compact pre-edit verdict (~50-150 tokens) vs full post-write lint+review cycle (~1500 tokens)
        naive_review_tokens = 1500
        tokens_saved = max(0, naive_review_tokens - resp_tokens)
        pct = round((tokens_saved / naive_review_tokens) * 100.0, 1)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        results.append(
            {
                "id": idx,
                "category": "prewrite_verify",
                "name": label,
                "expected_ok": expected_ok,
                "actual_ok": passed,
                "gate_accurate": passed == expected_ok,
                "raw_tokens": naive_review_tokens,
                "compressed_tokens": resp_tokens,
                "tokens_saved": tokens_saved,
                "savings_pct": pct,
                "elapsed_ms": ms,
            }
        )
        idx += 1

    return results


def main() -> int:
    comp_results = run_compression_suite()
    pre_results = run_prewrite_suite()
    all_results = comp_results + pre_results

    comp_raw = sum(r["raw_tokens"] for r in comp_results)
    comp_out = sum(r["compressed_tokens"] for r in comp_results)
    comp_saved = sum(r["tokens_saved"] for r in comp_results)
    comp_pct = round((comp_saved / comp_raw) * 100.0, 1) if comp_raw else 0.0

    pre_raw = sum(r["raw_tokens"] for r in pre_results)
    pre_out = sum(r["compressed_tokens"] for r in pre_results)
    pre_saved = sum(r["tokens_saved"] for r in pre_results)
    pre_pct = round((pre_saved / pre_raw) * 100.0, 1) if pre_raw else 0.0

    total_raw = comp_raw + pre_raw
    total_out = comp_out + pre_out
    total_saved = comp_saved + pre_saved
    total_pct = round((total_saved / total_raw) * 100.0, 1) if total_raw else 0.0

    payload = {
        "total_tests": len(all_results),
        "cli_compression": {
            "count": len(comp_results),
            "raw_tokens": comp_raw,
            "compressed_tokens": comp_out,
            "tokens_saved": comp_saved,
            "savings_pct": comp_pct,
        },
        "prewrite_gate": {
            "count": len(pre_results),
            "raw_tokens": pre_raw,
            "compressed_tokens": pre_out,
            "tokens_saved": pre_saved,
            "savings_pct": pre_pct,
        },
        "overall": {
            "raw_tokens": total_raw,
            "compressed_tokens": total_out,
            "tokens_saved": total_saved,
            "savings_pct": total_pct,
        },
        "tests": all_results,
    }

    out_json = AEDILE_ROOT / "benchmarks" / "token_savings_50_results.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    out_md = AEDILE_ROOT / "benchmarks" / "TOKEN_SAVINGS_50_TESTS.md"
    lines = [
        f"# Aedile Token Savings & Pre-Write Gate Benchmark ({len(all_results)} Real-World Tests)",
        "",
        "## Summary",
        "",
        "| Suite | Tests | Baseline Tokens | Aedile Tokens | Tokens Saved | Reduction |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **CLI Output Compression** (`aedile compress`) | {len(comp_results)} | {comp_raw:,} | {comp_out:,} | **{comp_saved:,}** | **{comp_pct}%** |",
        f"| **Pre-Write Gate** (`aedile_consult` + `verify`) | {len(pre_results)} | {pre_raw:,} | {pre_out:,} | **{pre_saved:,}** | **{pre_pct}%** |",
        f"| **Combined Total** | **{len(all_results)}** | **{total_raw:,}** | **{total_out:,}** | **{total_saved:,}** | **{total_pct}%** |",
        "",
        "## All 55 Test Runs",
        "",
        "| # | Category | Test | Filter / Check | Baseline Tok | Aedile Tok | Saved | Reduction | Time |",
        "| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in all_results:
        tag = r.get("filter", r["category"])
        lines.append(
            f"| {r['id']} | `{r['category']}` | {r['name']} | `{tag}` | "
            f"{r['raw_tokens']:,} | {r['compressed_tokens']:,} | {r['tokens_saved']:,} | "
            f"**{r['savings_pct']}%** | {r['elapsed_ms']}ms |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"[OK] {len(all_results)} tests complete | CLI saved {comp_saved:,}/{comp_raw:,} ({comp_pct}%) | "
        f"Pre-write saved {pre_saved:,}/{pre_raw:,} ({pre_pct}%)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
