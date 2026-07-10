import os
import re
from typing import Any

from aedile.core.models import SourceFile
from aedile.shared.config import Config


def tokenize(text: str) -> set[str]:
    """Tokenizes text by splitting camelCase, snake_case, and removing non-alphanumeric chars."""
    # Split camelCase
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.lower()
    # Replace symbols with spaces
    text = re.sub(r"[^a-z0-9]", " ", text)
    return {w for w in text.split() if len(w) > 1}


# Mapping of common concepts to Python Standard Library modules
STDLIB_MAP = {
    "hashlib": {"hash", "md5", "sha256", "sha1", "cryptography", "checksum"},
    "re": {"regex", "regular expression", "pattern match", "findall", "substitute"},
    "subprocess": {"subprocess", "run command", "execute command", "shell", "exec"},
    "json": {"json", "serialize json", "deserialize json", "parse json"},
    "datetime": {"datetime", "date", "time", "timezone", "timestamp"},
    "tempfile": {"temp file", "temporary file", "temp dir", "temporary directory"},
    "unittest.mock": {"mock", "patch", "spy", "double", "test double"},
    "pathlib": {"path", "filepath", "directory path", "join path", "glob"},
    "os": {"env var", "environment variable", "os walk", "makedirs", "remove file"},
    "math": {"sqrt", "ceil", "floor", "logarithm", "trigonometry", "factorial"},
    "csv": {"csv", "parse csv", "write csv", "comma separated"},
    "urllib.request": {"http request", "fetch url", "urllib", "download file"},
}

# Mapping of common concepts to popular third-party libraries (for dependency checking)
DEP_MAP = {
    "requests": {"http request", "fetch api", "download", "http client", "get post"},
    "rich": {"console print", "terminal color", "progress bar", "console table", "pretty print"},
    "click": {"cli", "command line", "argparse", "terminal options"},
    "typer": {"cli", "command line", "argparse", "type annotations cli"},
    "pyyaml": {"yaml", "parse yaml", "read yaml", "write yaml"},
    "pandas": {"dataframe", "csv parse dataframe", "data analysis", "table manipulation"},
    "numpy": {"matrix", "array", "numerical operations", "linear algebra"},
}


class SimilarityEngine:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.symbol_index: list[dict[str, Any]] = []

    def index_project(self, source_files: list[SourceFile]) -> None:
        """Indexes all public symbols in the project for similarity lookup."""
        self.symbol_index = []
        for sf in source_files:
            for sym in sf.symbols:
                if sym.is_private:
                    continue

                name_tokens = tokenize(sym.name)
                doc_tokens = tokenize(sym.docstring) if sym.docstring else set()

                self.symbol_index.append(
                    {
                        "name": sym.name,
                        "kind": sym.kind,
                        "filepath": sf.filepath,
                        "relative_path": sf.relative_path,
                        "line": sym.line,
                        "name_tokens": name_tokens,
                        "doc_tokens": doc_tokens,
                        "all_tokens": name_tokens | doc_tokens,
                    }
                )

    def search_symbols(self, query: str, threshold: float = 0.3) -> list[dict[str, Any]]:
        """Searches indexed symbols for semantic/lexical overlap based on query tokens."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        results = []
        for item in self.symbol_index:
            # Jaccard-like similarity on tokens
            intersection = query_tokens & item["all_tokens"]
            if not intersection:
                continue

            # Weight name tokens higher than docstring tokens
            name_intersection = query_tokens & item["name_tokens"]
            score = (len(name_intersection) * 1.5 + len(intersection - name_intersection)) / len(
                query_tokens
            )

            if score >= threshold:
                results.append(
                    {
                        "name": item["name"],
                        "kind": item["kind"],
                        "relative_path": item["relative_path"],
                        "line": item["line"],
                        "score": round(score, 2),
                    }
                )

        # Sort by match score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:5]

    def check_stdlib(self, query: str) -> list[dict[str, Any]]:
        """Identifies if a standard library module matches the requested capability."""
        query_text = query.lower()
        recommendations = []

        for module, keywords in STDLIB_MAP.items():
            for kw in keywords:
                if kw in query_text:
                    recommendations.append(
                        {
                            "module": module,
                            "keyword": kw,
                            "description": f"The Python standard library module '{module}' matches the concept '{kw}'.",
                        }
                    )
                    break  # Recommending the module once is enough
        return recommendations

    def check_dependencies(self, query: str, project_root: str) -> list[str]:
        """Checks if a matching package is already declared in project dependencies."""
        query_text = query.lower()
        matched_packages = []

        # Step 1: Detect target libraries based on query keywords
        for package, keywords in DEP_MAP.items():
            for kw in keywords:
                if kw in query_text:
                    matched_packages.append(package)
                    break

        if not matched_packages:
            return []

        # Step 2: Check if package exists in pyproject.toml or requirements.txt
        installed_recs = []
        deps_content = ""

        pyproject_path = os.path.join(project_root, "pyproject.toml")
        reqs_path = os.path.join(project_root, "requirements.txt")

        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, encoding="utf-8", errors="ignore") as f:
                    deps_content += f.read().lower()
            except Exception:
                pass
        if os.path.exists(reqs_path):
            try:
                with open(reqs_path, encoding="utf-8", errors="ignore") as f:
                    deps_content += f.read().lower()
            except Exception:
                pass

        for pkg in matched_packages:
            # Look for dependency in text (e.g. "requests" or "rich")
            if re.search(r"\b" + re.escape(pkg) + r"\b", deps_content):
                installed_recs.append(pkg)

        return installed_recs
