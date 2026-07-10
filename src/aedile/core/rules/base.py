import abc

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.shared.config import Config


class BaseRule(abc.ABC):
    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The identifier of the rule."""
        pass

    @abc.abstractmethod
    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        """Evaluates the rule against the parsed files and dependency graph.
        Returns a list of violations (if any).
        """
        pass
