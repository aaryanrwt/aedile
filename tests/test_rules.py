import os
import tempfile
import pytest
from aedile.core.graph import ArchitectureGraph
from aedile.core.models import Import, SourceFile, Symbol
from aedile.core.rules import (
    BoundaryRule,
    CycleRule,
    DeadCodeRule,
    DuplicateRule,
    LayerRule,
    NamingRule,
)
from aedile.shared.config import Config


@pytest.fixture
def base_config() -> Config:
    config = Config.default()
    # Configure layers
    config.layer_order = ["presentation", "domain"]
    config.layer_mappings = {
        "presentation": ["**/cli/**"],
        "domain": ["**/models/**"],
    }
    return config


def test_layer_rule(base_config: Config) -> None:
    # Presentation file imports domain -> OK
    # Domain file imports presentation -> VIOLATION
    sf_pres = SourceFile(
        filepath="/project/src/cli/cmd.py",
        relative_path="src/cli/cmd.py",
        file_hash="1",
        file_size=10,
        language="python",
        imports=[Import(module="models.entity", names=[], line=2)],
    )
    sf_dom = SourceFile(
        filepath="/project/src/models/entity.py",
        relative_path="src/models/entity.py",
        file_hash="2",
        file_size=10,
        language="python",
        imports=[Import(module="cli.cmd", names=[], line=1)], # VIOLATION: domain imports presentation
    )

    graph = ArchitectureGraph()
    graph.add_node("cli.cmd", sf_pres.filepath)
    graph.add_node("models.entity", sf_dom.filepath)
    graph.add_edge("cli.cmd", "models.entity")
    graph.add_edge("models.entity", "cli.cmd")

    rule = LayerRule(base_config)
    violations = rule.evaluate([sf_pres, sf_dom], graph)
    
    assert len(violations) == 1
    assert violations[0].rule_name == "layer_violations"
    assert "Layer 'domain' is not allowed to import from layer 'presentation'" in violations[0].message


def test_boundary_rule(base_config: Config) -> None:
    # Module 'cli._private' is package-private. 'models.entity' should not import it.
    sf_caller = SourceFile(
        filepath="/project/src/models/entity.py",
        relative_path="src/models/entity.py",
        file_hash="1",
        file_size=10,
        language="python",
        imports=[Import(module="cli._private_utils", names=[], line=2)],
    )

    graph = ArchitectureGraph()
    rule = BoundaryRule(base_config)
    violations = rule.evaluate([sf_caller], graph)

    assert len(violations) == 1
    assert violations[0].rule_name == "module_boundaries"
    assert "is private to 'cli'" in violations[0].message


def test_naming_rule(base_config: Config) -> None:
    # Setup custom naming convention for presentation
    from aedile.shared.config import NamingPattern
    base_config.naming_patterns = [
        NamingPattern(
            path_pattern="**/cli/**",
            class_pattern="^[A-Z][a-zA-Z0-9]*Command$",
            function_pattern="^[a-z_][a-z0-9_]*$",
            file_pattern="^[a-z_][a-z0-9_]*\\.py$",
        )
    ]

    # Valid name: CLICommand
    # Invalid class name: MyClass
    # Invalid file name: UpperName.py
    sf = SourceFile(
        filepath="/project/src/cli/UpperName.py",
        relative_path="src/cli/UpperName.py",
        file_hash="1",
        file_size=10,
        language="python",
        symbols=[
            Symbol(name="MyClass", kind="class", line=2, end_line=5),
            Symbol(name="CLICommand", kind="class", line=6, end_line=10),
            Symbol(name="valid_func", kind="function", line=12, end_line=15),
            Symbol(name="INVALID_FUNC", kind="function", line=17, end_line=20),
        ],
    )

    rule = NamingRule(base_config)
    violations = rule.evaluate([sf], ArchitectureGraph())

    # Should find: 1 file naming violation, 1 class naming violation, 1 function naming violation
    assert len(violations) == 3
    rule_names = [v.message for v in violations]
    assert any("File name 'UpperName.py'" in msg for msg in rule_names)
    assert any("Class 'MyClass'" in msg for msg in rule_names)
    assert any("Function 'INVALID_FUNC'" in msg for msg in rule_names)


def test_dead_code_rule(base_config: Config) -> None:
    # Set up symbols: one referenced in another file, one completely dead
    sf_def = SourceFile(
        filepath="/project/src/models/entity.py",
        relative_path="src/models/entity.py",
        file_hash="1",
        file_size=10,
        language="python",
        symbols=[
            Symbol(name="UsedClass", kind="class", line=2, end_line=5),
            Symbol(name="DeadClass", kind="class", line=6, end_line=10),
            Symbol(name="_private_unused", kind="class", line=11, end_line=12, is_private=True),
        ],
    )
    sf_use = SourceFile(
        filepath="/project/src/cli/cmd.py",
        relative_path="src/cli/cmd.py",
        file_hash="2",
        file_size=10,
        language="python",
        imports=[Import(module="models.entity", names=["UsedClass"], line=1)],
    )

    # Mock file contents to support regex text lookup
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f2:
        f1.write(b"class UsedClass:\n    pass\nclass DeadClass:\n    pass\nclass _private_unused:\n    pass\n")
        f2.write(b"from models.entity import UsedClass\n")
        sf_def.filepath = f1.name
        sf_use.filepath = f2.name

    try:
        rule = DeadCodeRule(base_config)
        violations = rule.evaluate([sf_def, sf_use], ArchitectureGraph())
        
        # DeadClass should be flagged as dead
        # _private_unused should be flagged as unused private symbol
        assert len(violations) == 2
        messages = [v.message for v in violations]
        assert any("Public symbol 'DeadClass'" in msg for msg in messages)
        assert any("Private symbol '_private_unused'" in msg for msg in messages)
    finally:
        os.remove(sf_def.filepath)
        os.remove(sf_use.filepath)


def test_duplicate_rule(base_config: Config) -> None:
    # Create two files with exact same contents to verify duplicate trigger
    code = "def my_function(x, y):\n    res = x + y\n    return res\n"
    
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f2:
        f1.write(code.encode("utf-8"))
        f2.write(code.encode("utf-8"))
        
        sf1 = SourceFile(filepath=f1.name, relative_path="src/a.py", file_hash="1", file_size=150, language="python")
        sf2 = SourceFile(filepath=f2.name, relative_path="src/b.py", file_hash="2", file_size=150, language="python")

    try:
        base_config.duplicate_min_file_size = 5
        base_config.duplicate_similarity_threshold = 0.8
        
        rule = DuplicateRule(base_config)
        violations = rule.evaluate([sf1, sf2], ArchitectureGraph())
        
        assert len(violations) == 1
        assert "Duplicate architecture" in violations[0].message
    finally:
        os.remove(sf1.filepath)
        os.remove(sf2.filepath)
