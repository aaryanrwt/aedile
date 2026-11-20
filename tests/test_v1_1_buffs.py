import json
import os
import sys
import tempfile

import pytest

from aedile.cli.setup import get_intensity_mode, set_intensity_mode, setup_agents
from aedile.core.baseline import BaselineManager
from aedile.core.debt import format_debt_ledger, scan_debt
from aedile.core.graph import ArchitectureGraph
from aedile.core.inference import infer_layers
from aedile.core.mapper import build_codebase_map
from aedile.core.models import Import, ProjectMetrics, Report, SourceFile, Symbol, Violation
from aedile.core.monorepo import check_cross_package_boundaries, discover_workspace_packages
from aedile.core.plugins import load_custom_rules
from aedile.core.polyglot import PolyglotParser
from aedile.core.reporter import to_html, to_json, to_sarif
from aedile.core.reviewer import format_review, review_changes
from aedile.core.rules.cycle import CycleRule
from aedile.core.verifier import ArchitectureVerifier
from aedile.infrastructure.telemetry import TelemetryStore
from aedile.infrastructure.watcher import WorkspaceWatcher
from aedile.mcp.server import AedileMcpServer
from aedile.shared.config import Config


def test_codebase_map_prioritizes_shared_within_budget() -> None:
    files = [
        SourceFile(
            filepath="/repo/src/features/billing.py",
            relative_path="src/features/billing.py",
            file_hash="a",
            file_size=10,
            language="python",
            symbols=[Symbol(name="charge_card", kind="function", line=1, end_line=5)],
        ),
        SourceFile(
            filepath="/repo/src/shared/auth.py",
            relative_path="src/shared/auth.py",
            file_hash="b",
            file_size=10,
            language="python",
            symbols=[Symbol(name="verify_jwt", kind="function", line=1, end_line=5)],
        ),
    ]
    out = build_codebase_map(files, Config(), budget_chars=120)
    assert "src/shared" in out
    assert "verify_jwt" in out


def test_infer_layers_and_baseline_and_reporters() -> None:
    files = [
        SourceFile(
            filepath="/r/src/cli/app.py",
            relative_path="src/cli/app.py",
            file_hash="1",
            file_size=1,
            language="python",
        ),
        SourceFile(
            filepath="/r/src/domain/user.py",
            relative_path="src/domain/user.py",
            file_hash="2",
            file_size=1,
            language="python",
        ),
        SourceFile(
            filepath="/r/src/shared/err.py",
            relative_path="src/shared/err.py",
            file_hash="3",
            file_size=1,
            language="python",
        ),
    ]
    cfg = infer_layers(files, Config())
    assert "presentation" in cfg.layer_order
    assert "domain" in cfg.layer_order
    assert "shared" in cfg.layer_order

    v1 = Violation(
        rule_name="cycle_detection",
        filepath="/r/a.py",
        relative_path="a.py",
        line=1,
        message="cycle",
    )
    v2 = Violation(
        rule_name="layer_violations",
        filepath="/r/b.py",
        relative_path="b.py",
        line=2,
        message="layer",
    )

    with tempfile.TemporaryDirectory() as tmp:
        bm = BaselineManager(tmp)
        bm.save([v1])
        new_v, suppressed = bm.filter_new([v1, v2])
        assert suppressed == 1
        assert len(new_v) == 1 and new_v[0].rule_name == "layer_violations"

    graph = ArchitectureGraph()
    graph.add_edge("a", "b")
    report = Report(
        project_name="Test",
        violations=[v1],
        metrics=ProjectMetrics(total_files=2, total_loc=20, total_violations=1, risk_score=5.0),
        generated_at="2026-11-20",
        scan_time_seconds=0.01,
    )
    assert json.loads(to_json(report))["project_name"] == "Test"
    assert json.loads(to_sarif(report))["version"] == "2.1.0"
    assert "<svg" in to_html(report, graph)


def test_verifier_delete_action_detects_dangling_import() -> None:
    cfg = Config()
    cfg.src_dirs = ["src"]
    verifier = ArchitectureVerifier(cfg)
    base_files = [
        SourceFile(
            filepath="/proj/src/shared/auth.py",
            relative_path="src/shared/auth.py",
            file_hash="1",
            file_size=10,
            language="python",
        ),
        SourceFile(
            filepath="/proj/src/app/routes.py",
            relative_path="src/app/routes.py",
            file_hash="2",
            file_size=10,
            language="python",
            imports=[Import(module="shared.auth", names=["login"], line=3)],
        ),
    ]
    violations = verifier.verify_changes(
        "/proj", base_files, [{"path": "src/shared/auth.py", "action": "delete"}]
    )
    assert any(v.rule_name == "dangling_import" for v in violations)


@pytest.mark.skipif(sys.version_info < (3, 15), reason="PEP 810 lazy imports require Python 3.15+")
def test_lazy_only_cycle_is_warning_with_hint() -> None:
    cfg = Config()
    cfg.src_dirs = ["src"]
    sf_a = SourceFile(
        filepath="/proj/src/a.py",
        relative_path="src/a.py",
        file_hash="1",
        file_size=10,
        language="python",
        imports=[Import(module="b", names=[], line=1, is_lazy=True)],
    )
    sf_b = SourceFile(
        filepath="/proj/src/b.py",
        relative_path="src/b.py",
        file_hash="2",
        file_size=10,
        language="python",
        imports=[Import(module="a", names=[], line=1, is_lazy=True)],
    )
    graph = ArchitectureGraph()
    graph.add_edge("a", "b", is_lazy=True)
    graph.add_edge("b", "a", is_lazy=True)
    violations = CycleRule(cfg).evaluate([sf_a, sf_b], graph)
    assert len(violations) == 2
    assert all(v.severity == "warning" for v in violations)
    assert "Hint:" in violations[0].message


def test_debt_ledger_and_blast_radius_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fpath = os.path.join(tmp, "worker.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(
                "# shortcut: polling every 5s, switch to inotify if >10k files\n# aedile-waive: legacy\n"
            )
        entries = scan_debt(tmp)
        assert len(entries) == 2
        assert entries[0].has_trigger is True
        assert entries[1].has_trigger is False
        ledger = format_debt_ledger(entries)
        assert "1 with no trigger" in ledger

    graph = ArchitectureGraph()
    for caller in ("c1", "c2", "c3"):
        graph.add_edge(caller, "core.db")
    sf_db = SourceFile(
        filepath="/p/src/core/db.py",
        relative_path="src/core/db.py",
        file_hash="1",
        file_size=1,
        language="python",
    )
    findings = review_changes("/p", [sf_db], graph, [], Config(), changed_paths=["src/core/db.py"])
    rendered = format_review(findings)
    assert "High blast radius" in rendered


def test_polyglot_parsers_ts_go_rust() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ts_path = os.path.join(tmp, "app.ts")
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write("import { x } from './util';\nexport function runApp() {}\n")
        sf_ts = PolyglotParser("typescript").parse(ts_path, tmp, ["."])
        assert sf_ts.imports[0].module == "util"
        assert sf_ts.imports[0].is_relative is True
        assert sf_ts.symbols[0].name == "runApp"

        go_path = os.path.join(tmp, "main.go")
        with open(go_path, "w", encoding="utf-8") as f:
            f.write('package main\nimport (\n  "fmt"\n)\nfunc Serve() {}\n')
        sf_go = PolyglotParser("go").parse(go_path, tmp, ["."])
        assert sf_go.imports[0].module == "fmt"
        assert sf_go.symbols[0].name == "Serve"

        rs_path = os.path.join(tmp, "lib.rs")
        with open(rs_path, "w", encoding="utf-8") as f:
            f.write("use crate::core::engine;\npub fn start() {}\n")
        sf_rs = PolyglotParser("rust").parse(rs_path, tmp, ["."])
        assert sf_rs.imports[0].module == "crate.core.engine"
        assert sf_rs.symbols[0].name == "start"


def test_plugins_monorepo_watcher_telemetry_and_setup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Custom plugin
        rules_dir = os.path.join(tmp, ".aedile", "rules")
        os.makedirs(rules_dir, exist_ok=True)
        with open(os.path.join(rules_dir, "custom.py"), "w", encoding="utf-8") as f:
            f.write(
                "from aedile.core.rules.base import BaseRule\n"
                "class NoTodoRule(BaseRule):\n"
                "    @property\n"
                "    def name(self):\n"
                "        return 'no_todo'\n"
                "    def evaluate(self, files, graph):\n"
                "        return []\n"
            )
        assert load_custom_rules(tmp, Config()) == []
        cfg_plugins = Config()
        cfg_plugins.allow_plugins = True
        plugins = load_custom_rules(tmp, cfg_plugins)
        assert len(plugins) == 1 and plugins[0].name == "no_todo"

        # Monorepo boundary
        pkg_a = os.path.join(tmp, "packages", "alpha")
        pkg_b = os.path.join(tmp, "packages", "beta")
        os.makedirs(pkg_a, exist_ok=True)
        os.makedirs(pkg_b, exist_ok=True)
        pkgs = discover_workspace_packages(tmp)
        assert "alpha" in pkgs and "beta" in pkgs
        sf = SourceFile(
            filepath=os.path.join(pkg_a, "main.py"),
            relative_path="packages/alpha/main.py",
            file_hash="1",
            file_size=1,
            language="python",
            imports=[Import(module="beta._secret", names=[], line=2)],
        )
        mono_v = check_cross_package_boundaries([sf], pkgs)
        assert len(mono_v) == 1 and mono_v[0].rule_name == "monorepo_boundary"

        # Watcher + Telemetry + Mode + Setup
        w = WorkspaceWatcher()
        assert w.has_changes([os.path.join(rules_dir, "custom.py")]) is True
        assert w.has_changes([os.path.join(rules_dir, "custom.py")]) is False

        t = TelemetryStore(tmp)
        t.record(
            "aedile_consult", reused_symbols=2, violations_prevented=1, estimated_tokens_saved=1200
        )
        assert "reused: 2" in t.statusline()
        assert "Aedile Local Telemetry Board" in t.render_board_html()

        set_intensity_mode(tmp, "ultra")
        assert get_intensity_mode(tmp) == "ultra"
        dry = setup_agents(tmp, dry_run=True)
        assert any("[dry-run]" in line for line in dry)

        # MCP server new tools
        src_dir = os.path.join(tmp, "src")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "app.py"), "w", encoding="utf-8") as f:
            f.write("def greet_user() -> str:\n    return 'hi'\n")
        srv = AedileMcpServer(tmp)
        assert "greet_user" in srv.handle_map({"budget": 500})["content"][0]["text"]
        assert (
            "0 violations"
            in srv.handle_verify_architecture({"proposed_changes": []})["content"][0]["text"]
        )
