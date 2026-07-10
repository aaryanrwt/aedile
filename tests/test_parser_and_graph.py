import os
import tempfile

from aedile.core.graph import ArchitectureGraph
from aedile.core.parser import (
    PythonParser,
    compute_module_name,
    resolve_relative_import,
)


def test_compute_module_name() -> None:
    # Test top-level module resolution
    m1 = compute_module_name(
        "c:/Users/User/project/src/aedile/core/scanner.py", "c:/Users/User/project", ["src"]
    )
    assert m1 == "aedile.core.scanner"

    # Test init package resolution
    m2 = compute_module_name(
        "c:/Users/User/project/src/aedile/__init__.py", "c:/Users/User/project", ["src"]
    )
    assert m2 == "aedile"


def test_resolve_relative_import() -> None:
    # Level 1 (sibling) import: inside 'aedile.core.scanner'
    res1 = resolve_relative_import("aedile.core.scanner", 1, "models")
    assert res1 == "aedile.core.models"

    # Level 2 (parent package sibling) import: inside 'aedile.core.scanner'
    res2 = resolve_relative_import("aedile.core.scanner", 2, "shared.errors")
    assert res2 == "aedile.shared.errors"

    # Level 1 import without module name: from . import x
    res3 = resolve_relative_import("aedile.core.scanner", 1, "")
    assert res3 == "aedile.core"


def test_python_ast_parser() -> None:
    code = """
import os
from sys import argv
from .models import SourceFile
from ..shared.errors import AedileError

class Scanner:
    \"\"\"Scanner class docstring.\"\"\"
    def run(self):
        pass

def global_fn():
    pass
"""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(code.encode("utf-8"))
        filepath = f.name

    try:
        parser = PythonParser()
        sf = parser.parse(filepath, os.path.dirname(filepath), [os.path.dirname(filepath)])

        # Verify imports
        assert len(sf.imports) == 4
        # Check absolute import
        assert sf.imports[0].module == "os"
        # Check relative resolution
        assert sf.imports[2].is_relative is True

        # Verify symbols
        classes = [s for s in sf.symbols if s.kind == "class"]
        funcs = [s for s in sf.symbols if s.kind == "function"]

        assert len(classes) == 1
        assert classes[0].name == "Scanner"
        assert classes[0].docstring == "Scanner class docstring."

        assert len(funcs) == 1
        assert funcs[0].name == "global_fn"
    finally:
        os.remove(filepath)


def test_architecture_graph_cycles() -> None:
    graph = ArchitectureGraph()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_node("C")
    graph.add_node("D")

    # Draw a cycle: A -> B -> C -> A
    graph.add_edge("A", "B")
    graph.add_edge("B", "C")
    graph.add_edge("C", "A")
    # Add an outlier
    graph.add_edge("C", "D")

    cycles = graph.find_all_cycles()
    assert len(cycles) == 1
    # Cycle should consist of A, B, C (order is maintained in cycle loop)
    assert set(cycles[0]) == {"A", "B", "C"}
    assert len(cycles[0]) == 3


def test_graph_exporters() -> None:
    graph = ArchitectureGraph()
    graph.add_node("aedile.core")
    graph.add_node("aedile.shared")
    graph.add_edge("aedile.core", "aedile.shared")

    # Test mermaid markup format
    mermaid = graph.export_mermaid()
    assert "graph TD" in mermaid
    assert "aedile_core --> aedile_shared" in mermaid

    # Test svg format
    svg = graph.export_svg()
    assert "<svg" in svg
    assert "aedile.core" in svg
