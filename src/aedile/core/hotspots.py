"""Zero-dependency cProfile hotspot profiler & outermost-caller ranker."""

from __future__ import annotations

import cProfile
import os
import pstats
import runpy
import sys
import time
from dataclasses import dataclass


@dataclass
class Hotspot:
    func_id: str
    filepath: str
    line: int
    name: str
    ncalls: int
    tottime: float
    cumtime: float
    share: float
    portability: float
    score: float
    covered_by: str | None = None


def _estimate_portability(filepath: str, name: str) -> float:
    if not filepath or filepath.startswith("<") or "site-packages" in filepath:
        return 0.0
    if name.startswith("<"):
        return 0.2
    return 1.0


def rank_hotspots(stats: pstats.Stats, wall_seconds: float, project_root: str) -> list[Hotspot]:
    """Ranks profiled functions by `cumtime_share * portability` and marks `covered_by`."""
    abs_root = os.path.abspath(project_root)
    raw_stats: dict[tuple[str, int, str], tuple[int, int, float, float, dict]] = getattr(
        stats, "stats", {}
    )
    items: list[Hotspot] = []

    for (filepath, line, name), (cc, nc, tt, ct, _callers) in raw_stats.items():
        if not filepath or not os.path.abspath(filepath).startswith(abs_root):
            continue
        rel = os.path.relpath(filepath, abs_root).replace(os.sep, "/")
        share = min(1.0, max(0.0, ct / wall_seconds)) if wall_seconds > 0 else 0.0
        port = _estimate_portability(filepath, name)
        score = round(share * port, 4)
        items.append(
            Hotspot(
                func_id=f"{rel}:{name}",
                filepath=rel,
                line=line,
                name=name,
                ncalls=nc or cc,
                tottime=round(tt, 5),
                cumtime=round(ct, 5),
                share=round(share, 4),
                portability=port,
                score=score,
            )
        )

    # Mark inner functions covered by an outermost caller in the same file
    for h in items:
        key_tuple = None
        for k in raw_stats:
            if (
                os.path.relpath(k[0], abs_root).replace(os.sep, "/") == h.filepath
                and k[1] == h.line
                and k[2] == h.name
            ):
                key_tuple = k
                break
        if key_tuple is None:
            continue
        callers = raw_stats[key_tuple][4]
        for caller_key in callers:
            c_rel = os.path.relpath(caller_key[0], abs_root).replace(os.sep, "/")
            if c_rel == h.filepath and caller_key[2] != h.name:
                c_ct = raw_stats.get(caller_key, (0, 0, 0.0, 0.0, {}))[3]
                c_share = c_ct / wall_seconds if wall_seconds > 0 else 0.0
                if c_share >= 0.9 * h.share and h.share > 0:
                    h.covered_by = f"{c_rel}:{caller_key[2]}"
                    h.score = 0.0
                    break

    items.sort(key=lambda x: (x.score, x.share, x.cumtime), reverse=True)
    return items


def profile_target(
    target_path: str, project_root: str, argv: list[str] | None = None
) -> tuple[float, list[Hotspot]]:
    """Profiles a Python script under cProfile and returns `(wall_seconds, ranked_hotspots)`."""
    abs_target = os.path.abspath(target_path)
    if not os.path.exists(abs_target):
        raise FileNotFoundError(f"Profile target not found: {target_path}")

    old_argv = sys.argv[:]
    sys.argv = [abs_target, *(argv or [])]
    profiler = cProfile.Profile()
    t0 = time.perf_counter()
    try:
        profiler.enable()
        runpy.run_path(abs_target, run_name="__main__")
    finally:
        profiler.disable()
        sys.argv = old_argv
    wall = max(1e-6, time.perf_counter() - t0)
    stats = pstats.Stats(profiler)
    return round(wall, 4), rank_hotspots(stats, wall, project_root)
