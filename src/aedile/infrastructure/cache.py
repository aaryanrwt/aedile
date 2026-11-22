import json
import os

from aedile.core.models import Import, SourceFile, Symbol
from aedile.shared.errors import CacheError
from aedile.shared.logging import get_logger

logger = get_logger("aedile.infrastructure.cache")

_DEFAULT_MAX_CACHE_BYTES = 64 * 1024 * 1024  # 64 MiB memory-bomb guard


def _max_cache_bytes() -> int:
    raw = os.environ.get("AEDILE_MAX_CACHE_BYTES", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return _DEFAULT_MAX_CACHE_BYTES


class ScanCache:
    def __init__(self, cache_filepath: str) -> None:
        if os.path.isdir(cache_filepath):
            cache_filepath = os.path.join(cache_filepath, ".aedile", "cache.json")
        self.cache_filepath = cache_filepath
        self.entries: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        """Loads cache from file. If it doesn't exist, exceeds size cap, or is corrupt, resets."""
        if not os.path.exists(self.cache_filepath):
            self.entries = {}
            return

        try:
            if os.path.getsize(self.cache_filepath) > _max_cache_bytes():
                logger.warning("Cache file exceeds AEDILE_MAX_CACHE_BYTES cap, resetting.")
                self.entries = {}
                return
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

    def get_by_stat(self, filepath: str, mtime_ns: int, file_size: int) -> SourceFile | None:
        """Fast-path cache lookup using (mtime_ns, file_size) without hashing file bytes."""
        entry = self.entries.get(filepath)
        if not entry:
            return None
        if entry.get("mtime_ns", 0) != mtime_ns or entry.get("file_size", -1) != file_size:
            return None
        if mtime_ns == 0:
            return None
        return self._reconstruct(filepath, entry)

    def get(self, filepath: str, current_hash: str) -> SourceFile | None:
        """Gets cached SourceFile if the file exists in the cache and the hash matches."""
        entry = self.entries.get(filepath)
        if not entry:
            return None

        if entry.get("file_hash") != current_hash:
            return None

        return self._reconstruct(filepath, entry)

    def _reconstruct(self, filepath: str, entry: dict) -> SourceFile | None:
        """Reconstruct SourceFile from dict representation."""
        try:
            imports = [
                Import(
                    module=imp["module"],
                    names=imp["names"],
                    line=imp["line"],
                    alias=imp.get("alias"),
                    is_relative=imp.get("is_relative", False),
                    is_lazy=imp.get("is_lazy", False),
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
                    signature=sym.get("signature"),
                    parent_name=sym.get("parent_name"),
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
                mtime_ns=entry.get("mtime_ns", 0),
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
                "is_lazy": imp.is_lazy,
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
                "signature": sym.signature,
                "parent_name": sym.parent_name,
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
            "mtime_ns": source_file.mtime_ns,
        }

    def clear(self) -> None:
        """Clears cache memory and deletes file."""
        self.entries = {}
        if os.path.exists(self.cache_filepath):
            try:
                os.remove(self.cache_filepath)
            except Exception as e:
                logger.warning(f"Could not delete cache file: {e}")
