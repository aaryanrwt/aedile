import os
import re

from aedile.core.graph import ArchitectureGraph
from aedile.core.models import SourceFile, Violation
from aedile.core.rules.base import BaseRule


class DuplicateRule(BaseRule):
    @property
    def name(self) -> str:
        return "duplicate_architecture"

    def _get_words_set(self, filepath: str) -> set[str]:
        """Cleans and extracts unique words from the file for structural similarity comparison."""
        if not os.path.exists(filepath):
            return set()
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Remove comments and strings to compare logic structure
            content_no_comments = re.sub(r"#.*", "", content)
            content_no_strings = re.sub(
                r'""".*?"""|\'\'\'.*?\'\'\'|"[^"]*"|\'[^\']*\'',
                "",
                content_no_comments,
                flags=re.DOTALL,
            )
            words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", content_no_strings)
            return set(words)
        except Exception:
            return set()

    def evaluate(self, files: list[SourceFile], graph: ArchitectureGraph) -> list[Violation]:
        violations: list[Violation] = []
        if not self.config.duplicate_architecture:
            return violations

        # Filter out small files, test files, and __init__.py files
        eligible_files = []
        word_sets = {}

        for sf in files:
            if sf.file_size < self.config.duplicate_min_file_size:
                continue
            if (
                "test" in sf.relative_path
                or "example" in sf.relative_path
                or sf.filepath.endswith("__init__.py")
            ):
                continue

            w_set = self._get_words_set(sf.filepath)
            if len(w_set) > 5:  # Only compare if file has sufficient tokens
                eligible_files.append(sf)
                word_sets[sf.filepath] = w_set

        # Compare pairs of files
        num_files = len(eligible_files)
        reported_pairs = set()

        for i in range(num_files):
            sf_a = eligible_files[i]
            set_a = word_sets[sf_a.filepath]

            for j in range(i + 1, num_files):
                sf_b = eligible_files[j]

                # Skip comparing files of different languages
                if sf_a.language != sf_b.language:
                    continue

                set_b = word_sets[sf_b.filepath]

                # Jaccard Similarity index calculation
                union_len = len(set_a.union(set_b))
                if union_len == 0:
                    continue

                similarity = len(set_a.intersection(set_b)) / union_len

                if similarity >= self.config.duplicate_similarity_threshold:
                    # Avoid duplicate warnings: sort paths to form a unique key
                    pair_key = tuple(sorted([sf_a.relative_path, sf_b.relative_path]))
                    if pair_key in reported_pairs:
                        continue
                    reported_pairs.add(pair_key)

                    # Highlight the structural similarity
                    violations.append(
                        Violation(
                            rule_name=self.name,
                            filepath=sf_a.filepath,
                            relative_path=sf_a.relative_path,
                            line=1,
                            message=(
                                f"Duplicate architecture: High structural similarity ({similarity * 100:.1f}%) "
                                f"detected between '{sf_a.relative_path}' and '{sf_b.relative_path}'."
                            ),
                            offending_symbol=sf_b.relative_path,
                            confidence=round(similarity, 2),
                            severity="warning",
                        )
                    )

        return violations
