import pytest

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import Import, SourceFile
from aedile.core.rules.cycle import CycleRule
from aedile.shared.config import Config
from aedile.shared.errors import ConfigError


def test_cycle_rule_evaluation() -> None:
    config = Config.default()
    config.cycle_detection = True
    config.src_dirs = ["src"]

    # File A imports B, File B imports A
    sf_a = SourceFile(
        filepath="/project/src/a.py",
        relative_path="src/a.py",
        file_hash="1",
        file_size=10,
        language="python",
        imports=[Import(module="b", names=[], line=1)],
    )
    sf_b = SourceFile(
        filepath="/project/src/b.py",
        relative_path="src/b.py",
        file_hash="2",
        file_size=10,
        language="python",
        imports=[Import(module="a", names=[], line=1)],
    )

    graph = ArchitectureGraph()
    graph.add_node("a", sf_a.filepath)
    graph.add_node("b", sf_b.filepath)
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")

    rule = CycleRule(config)
    violations = rule.evaluate([sf_a, sf_b], graph)
    assert len(violations) >= 2  # Violation reported at import in both files


def test_config_validation_failures() -> None:
    config = Config()

    # Trigger name type failure
    config.project_name = ""
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger src_dirs failure
    config.project_name = "ValidName"
    config.src_dirs = [123]  # type: ignore
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger exclude failure
    config.src_dirs = ["src"]
    config.exclude = [123]  # type: ignore
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger languages failure
    config.exclude = []
    config.languages = [123]  # type: ignore
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger layer order failure
    config.languages = ["python"]
    config.layer_order = [123]  # type: ignore
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger layer mappings failure
    config.layer_order = ["presentation"]
    config.layer_mappings = {123: ["**/cli/**"]}  # type: ignore
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger missing mappings in layer order validation
    config.layer_mappings = {}
    with pytest.raises(ConfigError):
        config.validate()

    # Trigger private prefixes validation failure
    config.layer_mappings = {"presentation": ["**/cli/**"]}
    config.private_prefixes = [123]  # type: ignore
    with pytest.raises(ConfigError):
        config.validate()
