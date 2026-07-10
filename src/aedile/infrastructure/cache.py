import json
import os

from aedile.core.models import Import, SourceFile, Symbol
from aedile.shared.errors import CacheError
from aedile.shared.logging import get_logger

logger = get_logger("aedile.infrastructure.cache")


class ScanCache:
    def __init__(self, cache_filepath: str) -> None:
        self.cache_filepath = cache_filepath
        self.entries: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        """Loads cache from file. If it doesn't exist or is corrupt, initializes an empty cache."""
        if not os.path.exists(self.cache_filepath):
            self.entries = {}
            return

        try:
            with open(self.cache_filepath, encoding="utf-8") as f:
                self.entries = json.load(f)
        except Exception as e:
            logger.warning(f"Cache file corrupt or unreadable, resetting: {e}")
            self.entries = {}

    def save(self) -> None:
        """Saves current cache entries to the cache file."""
        try:
            # Ensure folder exists
            parent_dir = os.path.dirname(self.cache_filepath)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            with open(self.cache_filepath, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            raise CacheError(f"Failed to write scan cache to {self.cache_filepath}: {e}")

    def get(self, filepath: str, current_hash: str) -> SourceFile | None:
        """Gets cached SourceFile if the file exists in the cache and the hash matches."""
        entry = self.entries.get(filepath)
        if not entry:
            return None

        if entry.get("file_hash") != current_hash:
            return None

        # Reconstruct SourceFile from dict representation
        try:
            imports = [
                Import(
                    module=imp["module"],
                    names=imp["names"],
                    line=imp["line"],
                    alias=imp.get("alias"),
                    is_relative=imp.get("is_relative", False),
                )
                for imp in entry.get("imports", [])
            ]

            symbols = [
                Symbol(
                    name=sym["name"],
                    kind=sym["kind"],
                    line=sym["line"],
                    end_line=sym["end_line"],
                    docstring=sym.get("docstring"),
                    is_private=sym.get("is_private", False),
                )
                for sym in entry.get("symbols", [])
            ]

            return SourceFile(
                filepath=entry["filepath"],
                relative_path=entry["relative_path"],
                file_hash=entry["file_hash"],
                file_size=entry["file_size"],
                language=entry["language"],
                imports=imports,
                symbols=symbols,
            )
        except Exception as e:
            logger.debug(f"Failed to deserialize cache entry for {filepath}: {e}")
            return None

    def set(self, filepath: str, source_file: SourceFile) -> None:
        """Puts a SourceFile into the cache."""
        # Convert imports and symbols to serializable dictionaries
        imports_data = [
            {
                "module": imp.module,
                "names": imp.names,
                "line": imp.line,
                "alias": imp.alias,
                "is_relative": imp.is_relative,
            }
            for imp in source_file.imports
        ]

        symbols_data = [
            {
                "name": sym.name,
                "kind": sym.kind,
                "line": sym.line,
                "end_line": sym.end_line,
                "docstring": sym.docstring,
                "is_private": sym.is_private,
            }
            for sym in source_file.symbols
        ]

        self.entries[filepath] = {
            "filepath": source_file.filepath,
            "relative_path": source_file.relative_path,
            "file_hash": source_file.file_hash,
            "file_size": source_file.file_size,
            "language": source_file.language,
            "imports": imports_data,
            "symbols": symbols_data,
        }

    def clear(self) -> None:
        """Clears cache memory and deletes file."""
        self.entries = {}
        if os.path.exists(self.cache_filepath):
            try:
                os.remove(self.cache_filepath)
            except Exception as e:
                logger.warning(f"Could not delete cache file: {e}")
