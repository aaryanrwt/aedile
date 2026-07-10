import os
import tempfile
import pytest
from aedile.shared.config import Config
from aedile.shared.errors import ConfigError


def test_default_config() -> None:
    config = Config.default()
    assert config.project_name == "Aedile"
    assert config.src_dirs == ["src"]
    assert config.cycle_detection is True


def test_load_valid_config() -> None:
    toml_content = """
    [project]
    name = "CustomTest"
    src_dirs = ["lib", "app"]
    exclude = ["**/tests/**"]
    languages = ["python"]
    confidence_threshold = 0.8

    [layers]
    order = ["web", "logic"]
    mappings = { web = ["**/web/**"], logic = ["**/logic/**"] }

    [rules]
    cycle_detection = true
    layer_violations = false
    """
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(toml_content.encode("utf-8"))
        temp_path = f.name

    try:
        config = Config.load_from_file(temp_path)
        assert config.project_name == "CustomTest"
        assert config.src_dirs == ["lib", "app"]
        assert config.exclude == ["**/tests/**"]
        assert config.confidence_threshold == 0.8
        assert config.layer_order == ["web", "logic"]
        assert config.layer_mappings == {"web": ["**/web/**"], "logic": ["**/logic/**"]}
        assert config.cycle_detection is True
        assert config.layer_violations is False
    finally:
        os.remove(temp_path)


def test_load_invalid_config() -> None:
    # Invalid confidence threshold
    toml_content = """
    [project]
    confidence_threshold = 1.5
    """
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(toml_content.encode("utf-8"))
        temp_path = f.name

    try:
        with pytest.raises(ConfigError):
            Config.load_from_file(temp_path)
    finally:
        os.remove(temp_path)
