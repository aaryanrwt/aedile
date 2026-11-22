"""Automated physics, collision, and 1,000-frame zero-lag benchmark for Tesla Roadster game."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from entities import WorldManager  # noqa: E402
from physics import InputState, RoadsterState, roadster_hits_box, step_roadster  # noqa: E402


def test_flight_physics_and_collision() -> None:
    state = RoadsterState()
    initial_y = state.y
    step_roadster(state, InputState(thrust_up=True, boost=True), 0.016)
    assert state.boosting is True
    assert state.battery < 100.0
    assert state.speed_kmh > 280.0
    assert state.score > 0.0
    assert state.y <= initial_y + 5.0

    assert roadster_hits_box(state, state.x, state.y, 40.0, 20.0) is True
    assert roadster_hits_box(state, state.x + 500.0, state.y, 40.0, 20.0) is False


def test_1000_frames_zero_lag_simulation() -> None:
    state = RoadsterState()
    world = WorldManager(seed=42)
    t0 = time.perf_counter()
    for i in range(1000):
        controls = InputState(thrust_up=(i % 3 == 0), boost=(i % 5 == 0))
        step_roadster(state, controls, 1.0 / 60.0)
        world.emit_thruster(state.x, state.y, state.boosting)
        world.step(1.0 / 60.0, state.speed_kmh * 1.15)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    per_frame_ms = elapsed_ms / 1000.0
    assert per_frame_ms < 2.0, f"Too slow: {per_frame_ms:.3f} ms/frame"
    assert len(world.particles) <= 95
    print(f"[OK] 1,000 frames simulated in {elapsed_ms:.1f}ms ({per_frame_ms:.4f} ms/frame)")


if __name__ == "__main__":
    test_flight_physics_and_collision()
    test_1000_frames_zero_lag_simulation()
