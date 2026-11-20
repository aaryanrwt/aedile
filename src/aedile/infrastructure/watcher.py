import os


class WorkspaceWatcher:
    """Zero-dependency incremental file watcher using (mtime_ns, size) snapshots."""

    def __init__(self) -> None:
        self._snapshot: dict[str, tuple[int, int]] = {}

    def diff(self, filepaths: list[str]) -> tuple[list[str], list[str]]:
        """Compares current file stats against the previous snapshot.

        Returns `(changed_or_added, deleted)`.
        """
        current: dict[str, tuple[int, int]] = {}
        changed: list[str] = []

        for fp in filepaths:
            try:
                st = os.stat(fp)
                sig = (st.st_mtime_ns, st.st_size)
                current[fp] = sig
                if self._snapshot.get(fp) != sig:
                    changed.append(fp)
            except OSError:
                continue

        deleted = [fp for fp in self._snapshot if fp not in current]
        self._snapshot = current
        return changed, deleted

    def has_changes(self, filepaths: list[str]) -> bool:
        changed, deleted = self.diff(filepaths)
        return bool(changed or deleted)
