"""Comprehensive 1,000+ case parameterized test suite for Aedile v1.1.0."""

from __future__ import annotations

import os
import tempfile

import pytest

from aedile.core.baseline import BaselineManager
from aedile.core.debt import scan_debt
from aedile.core.graph import ArchitectureGraph
from aedile.core.graph_insights import (
    detect_communities,
    explain_module,
    god_nodes,
    graph_diff,
    suggest_questions,
    surprising_connections,
)
from aedile.core.mapper import build_codebase_map
from aedile.core.models import Import, ProjectMetrics, Report, SourceFile, Symbol, Violation
from aedile.core.parser import PythonParser, compute_module_name, resolve_relative_import
from aedile.core.polyglot import PolyglotParser
from aedile.core.reporter import to_card_svg, to_html, to_json, to_sarif
from aedile.core.rules.boundary import BoundaryRule
from aedile.core.rules.cycle import CycleRule
from aedile.core.rules.layer import LayerRule
from aedile.core.rules.naming import NamingRule
from aedile.core.similarity import STDLIB_MAP, SimilarityEngine, tokenize
from aedile.core.verifier import ArchitectureVerifier
from aedile.infrastructure.cache import ScanCache
from aedile.mcp.server import AedileMcpServer
from aedile.shared.config import Config, NamingPattern
from aedile.shared.errors import ConfigError

# 1. 120 module-name resolution cases
_MODULE_CASES = [
    (f"/proj/src/pkg{i}/mod{j}.py", f"pkg{i}.mod{j}") for i in range(12) for j in range(10)
]


@pytest.mark.parametrize(("fpath", "expected"), _MODULE_CASES)
def test_compute_module_name_matrix(fpath: str, expected: str) -> None:
    assert compute_module_name(fpath, "/proj", ["src"]) == expected


# 2. 100 relative-import resolution cases
_REL_CASES = [("a.b.c.d", 1, f"m{i}", f"a.b.c.m{i}") for i in range(50)] + [
    ("a.b.c.d", 2, f"sub.m{i}", f"a.b.sub.m{i}") for i in range(50)
]


@pytest.mark.parametrize(("src_mod", "level", "target", "expected"), _REL_CASES)
def test_resolve_relative_import_matrix(
    src_mod: str, level: int, target: str, expected: str
) -> None:
    assert resolve_relative_import(src_mod, level, target) == expected


# 3. 150 similarity & stdlib cases
_STDLIB_CASES = [(kw, mod) for mod, kws in STDLIB_MAP.items() for kw in sorted(kws)]
while len(_STDLIB_CASES) < 150:
    _STDLIB_CASES.extend(_STDLIB_CASES[: 150 - len(_STDLIB_CASES)])
_STDLIB_CASES = _STDLIB_CASES[:150]


@pytest.mark.parametrize(("query", "expected_mod"), _STDLIB_CASES)
def test_similarity_stdlib_and_tokenize_matrix(query: str, expected_mod: str) -> None:
    eng = SimilarityEngine(Config())
    recs = eng.check_stdlib(f"need helper to {query}")
    assert any(r["module"] == expected_mod for r in recs)
    assert len(tokenize(f"camelCaseHelper_{query.replace(' ', '_')}")) >= 2


# 4. 160 graph topology, cycle, blast-radius, insights & exporter cases
@pytest.mark.parametrize("n_nodes", range(2, 42))
def test_graph_cycle_detection_sizes(n_nodes: int) -> None:
    g = ArchitectureGraph()
    for i in range(n_nodes):
        g.add_edge(f"m{i}", f"m{(i + 1) % n_nodes}")
    cycles = g.find_all_cycles()
    assert len(cycles) == 1 and len(cycles[0]) == n_nodes
    assert len(g.get_blast_radius("m0")) == n_nodes - 1
    assert g.get_coupling_metrics("m0")["instability"] == 0.5


@pytest.mark.parametrize("n_nodes", range(3, 43))
def test_graph_dag_paths_and_insights(n_nodes: int) -> None:
    g = ArchitectureGraph()
    for i in range(n_nodes - 1):
        g.add_edge(f"n{i}", f"n{i + 1}")
    assert g.find_all_cycles() == []
    path = g.find_shortest_path("n0", f"n{n_nodes - 1}")
    assert path is not None and len(path) == n_nodes
    hubs = god_nodes(g, top_n=2)
    assert len(hubs) >= 1
    comms = detect_communities(g)
    assert len(comms) >= 1
    _ = surprising_connections(g, comms)
    assert len(suggest_questions(g, comms)) >= 1
    assert explain_module(g, "n1")["found"] is True


@pytest.mark.parametrize("edge_count", range(1, 81))
def test_graph_exporters_matrix(edge_count: int) -> None:
    g = ArchitectureGraph()
    for i in range(edge_count):
        g.add_edge(f"pkg.a{i}", f"pkg.b{i}", is_lazy=(i % 2 == 0))
    assert "graph TD" in g.export_mermaid()
    assert "<svg" in g.export_svg()
    assert "<graphml" in g.export_graphml()
    assert "MERGE (:Module" in g.export_cypher()


# 5. 160 polyglot parser cases (TS, JS, Go, Rust)
_POLY_CASES = (
    [
        (
            "typescript",
            f"app{i}.ts",
            f"import {{ fn{i} }} from './mod{i}';\nexport function run{i}() {{}}\n",
            f"mod{i}",
            f"run{i}",
        )
        for i in range(40)
    ]
    + [
        (
            "javascript",
            f"app{i}.js",
            f"const x = require('./lib{i}');\nexport class Cls{i} {{}}\n",
            f"lib{i}",
            f"Cls{i}",
        )
        for i in range(40)
    ]
    + [
        (
            "go",
            f"m{i}.go",
            f'package main\nimport "pkg/v{i}"\nfunc Serve{i}() {{}}\n',
            f"pkg/v{i}",
            f"Serve{i}",
        )
        for i in range(40)
    ]
    + [
        (
            "rust",
            f"r{i}.rs",
            f"use crate::core::m{i};\npub fn exec_{i}() {{}}\n",
            f"crate.core.m{i}",
            f"exec_{i}",
        )
        for i in range(40)
    ]
)


@pytest.mark.parametrize(("lang", "fname", "code", "exp_imp", "exp_sym"), _POLY_CASES)
def test_polyglot_parsers_matrix(
    lang: str, fname: str, code: str, exp_imp: str, exp_sym: str
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, fname)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(code)
        sf = PolyglotParser(lang).parse(fp, tmp, ["."])
        assert any(imp.module == exp_imp for imp in sf.imports)
        assert any(sym.name == exp_sym for sym in sf.symbols)


# 6. 200 rule, verifier & security cases
@pytest.mark.parametrize("idx", range(50))
def test_verifier_path_traversal_matrix(idx: int) -> None:
    cfg = Config()
    verifier = ArchitectureVerifier(cfg)
    payloads = [f"../escape_{idx}.py", f"../../etc/passwd_{idx}", f"sub/../../../out_{idx}.py"]
    for bad in payloads:
        res = verifier.verify_changes("/safe/root", [], [{"path": bad, "action": "add"}])
        assert len(res) == 1 and res[0].rule_name == "security_check"


@pytest.mark.parametrize("idx", range(50))
def test_layer_rule_violation_matrix(idx: int) -> None:
    cfg = Config()
    cfg.src_dirs = ["src"]
    cfg.layer_order = ["presentation", "domain"]
    cfg.layer_mappings = {"presentation": ["**/cli/**"], "domain": ["**/core/**"]}
    sf_cli = SourceFile(
        filepath=f"/p/src/cli/c{idx}.py",
        relative_path=f"src/cli/c{idx}.py",
        file_hash="1",
        file_size=10,
        language="python",
    )
    sf_dom = SourceFile(
        filepath=f"/p/src/core/d{idx}.py",
        relative_path=f"src/core/d{idx}.py",
        file_hash="2",
        file_size=10,
        language="python",
        imports=[Import(module=f"cli.c{idx}", names=[], line=1)],
    )
    g = ArchitectureGraph()
    g.add_edge(f"core.d{idx}", f"cli.c{idx}")
    vs = LayerRule(cfg).evaluate([sf_cli, sf_dom], g)
    assert len(vs) == 1 and vs[0].rule_name == "layer_violations"


@pytest.mark.parametrize("idx", range(50))
def test_boundary_and_naming_rules_matrix(idx: int) -> None:
    cfg = Config()
    cfg.src_dirs = ["src"]
    cfg.naming_patterns = [
        NamingPattern(path_pattern="**/cli/**", class_pattern="^[A-Z].*Command$")
    ]
    sf_a = SourceFile(
        filepath=f"/p/src/cli/bad{idx}.py",
        relative_path=f"src/cli/bad{idx}.py",
        file_hash="1",
        file_size=10,
        language="python",
        imports=[Import(module=f"core._secret{idx}", names=[], line=1)],
        symbols=[Symbol(name=f"BadName{idx}", kind="class", line=2, end_line=4)],
    )
    g = ArchitectureGraph()
    assert len(BoundaryRule(cfg).evaluate([sf_a], g)) == 1
    assert len(NamingRule(cfg).evaluate([sf_a], g)) == 1


@pytest.mark.parametrize("idx", range(50))
def test_cycle_rule_lazy_vs_eager_matrix(idx: int) -> None:
    cfg = Config()
    cfg.src_dirs = ["src"]
    is_lazy = idx % 2 == 0
    sf1 = SourceFile(
        filepath=f"/p/src/a{idx}.py",
        relative_path=f"src/a{idx}.py",
        file_hash="1",
        file_size=10,
        language="python",
        imports=[Import(module=f"b{idx}", names=[], line=1, is_lazy=is_lazy)],
    )
    sf2 = SourceFile(
        filepath=f"/p/src/b{idx}.py",
        relative_path=f"src/b{idx}.py",
        file_hash="2",
        file_size=10,
        language="python",
        imports=[Import(module=f"a{idx}", names=[], line=1, is_lazy=is_lazy)],
    )
    g = ArchitectureGraph()
    g.add_edge(f"a{idx}", f"b{idx}", is_lazy=is_lazy)
    g.add_edge(f"b{idx}", f"a{idx}", is_lazy=is_lazy)
    vs = CycleRule(cfg).evaluate([sf1, sf2], g)
    assert len(vs) == 2
    assert all(v.severity == ("warning" if is_lazy else "error") for v in vs)


# 7. 150 debt, baseline, cache, reporters, parser, config & MCP cases
@pytest.mark.parametrize("idx", range(50))
def test_debt_and_baseline_matrix(idx: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, f"mod{idx}.py")
        with open(fp, "w", encoding="utf-8") as f:
            if idx % 2 == 0:
                f.write(f"# shortcut: limit {idx}, upgrade at scale {idx}\n")
            else:
                f.write(f"# shortcut: limit {idx}\n")
        entries = scan_debt(tmp)
        assert len(entries) == 1
        assert entries[0].has_trigger is (idx % 2 == 0)

        v = Violation(
            rule_name="layer_violations",
            filepath=fp,
            relative_path=f"mod{idx}.py",
            line=1,
            message=f"msg {idx}",
            offending_symbol=f"sym{idx}",
        )
        bm = BaselineManager(tmp)
        bm.save([v])
        new_v, sup = bm.filter_new([v])
        assert new_v == [] and sup == 1


@pytest.mark.parametrize("idx", range(50))
def test_python_parser_cache_and_mapper_matrix(idx: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src_dir = os.path.join(tmp, "src", "shared")
        os.makedirs(src_dir, exist_ok=True)
        fp = os.path.join(src_dir, f"helper_{idx}.py")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(
                f"MAX_VAL_{idx} = {idx}\ndef compute_{idx}(x: int) -> int:\n    return x + {idx}\n"
            )
        sf = PythonParser().parse(fp, tmp, ["src"])
        assert any(s.name == f"compute_{idx}" for s in sf.symbols)
        assert any(s.name == f"MAX_VAL_{idx}" and s.kind == "constant" for s in sf.symbols)

        cache = ScanCache(os.path.join(tmp, ".aedile", "cache.json"))
        cache.set(fp, sf)
        cache.save()
        assert cache.get_by_stat(fp, sf.mtime_ns, sf.file_size) is not None
        assert f"compute_{idx}" in build_codebase_map([sf], Config(), budget_chars=500)


@pytest.mark.parametrize("idx", range(50))
def test_reporters_config_diff_and_mcp_guards(idx: int) -> None:
    with pytest.raises(ConfigError):
        NamingPattern(path_pattern="**", class_pattern="a" * (513 + idx))

    g_old = ArchitectureGraph()
    g_old.add_edge(f"a{idx}", f"b{idx}")
    g_new = ArchitectureGraph()
    g_new.add_edge(f"a{idx}", f"b{idx}")
    g_new.add_edge(f"b{idx}", f"c{idx}")
    diff = graph_diff(g_old, g_new)
    assert f"c{idx}" in diff["added_nodes"]

    rep = Report(
        project_name=f"Proj{idx}",
        violations=[],
        metrics=ProjectMetrics(total_files=idx + 1, total_loc=(idx + 1) * 10),
        generated_at="2026-11-22",
        scan_time_seconds=0.01,
    )
    assert f"Proj{idx}" in to_json(rep)
    assert "2.1.0" in to_sarif(rep)
    assert "<svg" in to_html(rep, g_new)
    assert "<svg" in to_card_svg(rep)

    with tempfile.TemporaryDirectory() as tmp:
        srv = AedileMcpServer(tmp)
        res = srv.handle_hotspots({"script": "../outside.py"})
        assert res.get("isError") is True
