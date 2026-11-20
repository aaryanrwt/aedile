import importlib.util
import os

from aedile.core.rules.base import BaseRule
from aedile.shared.config import Config
from aedile.shared.logging import get_logger

logger = get_logger("aedile.core.plugins")


def load_custom_rules(
    project_root: str, config: Config, allow_untrusted: bool = False
) -> list[BaseRule]:
    """Loads custom BaseRule subclasses from `.aedile/rules/*.py` when explicitly enabled."""
    if not (allow_untrusted or getattr(config, "allow_plugins", False)):
        return []

    rules_dir = os.path.realpath(os.path.join(os.path.abspath(project_root), ".aedile", "rules"))
    if not os.path.isdir(rules_dir):
        return []

    loaded: list[BaseRule] = []
    for fname in sorted(os.listdir(rules_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.realpath(os.path.join(rules_dir, fname))
        if not fpath.startswith(rules_dir + os.sep):
            logger.warning(f"Blocked symlinked plugin outside rules directory: {fname}")
            continue
        spec = importlib.util.spec_from_file_location(f"aedile_plugin_{fname[:-3]}", fpath)
        if not spec or not spec.loader:
            continue
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseRule)
                    and attr is not BaseRule
                ):
                    loaded.append(attr(config))
        except Exception as e:
            logger.warning(f"Failed loading custom rule plugin {fpath}: {e}")

    return loaded
