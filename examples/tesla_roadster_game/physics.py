"""Delta-time flight physics and collision math for Tesla Roadster."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    BASE_SPEED_KMH,
    BATTERY_DRAIN_PER_SEC,
    BATTERY_MAX,
    BATTERY_REGEN_PER_SEC,
    BOOST_SPEED_KMH,
    DIVE_ACCEL,
    GRAVITY,
    MAX_VY,
    ROADSTER_H,
    ROADSTER_W,
    ROADSTER_X,
    THRUST_ACCEL,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)


@dataclass
class RoadsterState:
    """Mutable flight state of the player's flying Tesla Roadster."""

    x: float = ROADSTER_X
    y: float = WINDOW_HEIGHT * 0.45
    vx_offset: float = 0.0
    vy: float = 0.0
    pitch_deg: float = 0.0
    battery: float = BATTERY_MAX
    boosting: bool = False
    speed_kmh: float = BASE_SPEED_KMH
    score: float = 0.0
    combo: int = 1
    alive: bool = True
    invuln_timer: float = 0.0


@dataclass(frozen=True)
class InputState:
    """Snapshot of active player controls."""

    thrust_up: bool = False
    dive_down: bool = False
    move_left: bool = False
    move_right: bool = False
    boost: bool = False


def step_roadster(state: RoadsterState, controls: InputState, dt: float) -> None:
    """Advance Roadster flight physics by dt seconds (clamped for stability)."""
    if not state.alive:
        return
    dt = min(max(dt, 0.0), 0.05)

    # Vertical acceleration: gravity vs SpaceX cold-gas thrusters
    ay = GRAVITY
    if controls.thrust_up:
        ay -= THRUST_ACCEL
    if controls.dive_down:
        ay += DIVE_ACCEL

    state.vy = max(-MAX_VY, min(MAX_VY, state.vy + ay * dt))
    state.y += state.vy * dt

    # Horizontal air-brake / dash within safe viewport bounds
    target_vx = 0.0
    if controls.move_left:
        target_vx -= 260.0
    if controls.move_right:
        target_vx += 260.0
    state.vx_offset += (target_vx - state.vx_offset) * min(1.0, 10.0 * dt)
    state.x = max(70.0, min(WINDOW_WIDTH * 0.65, state.x + state.vx_offset * dt))

    # Clamp altitude to sky & skyline floor
    min_y = 48.0
    max_y = WINDOW_HEIGHT - 56.0
    if state.y < min_y:
        state.y = min_y
        state.vy = max(0.0, state.vy)
    elif state.y > max_y:
        state.y = max_y
        state.vy = min(0.0, state.vy)

    # Super-boost battery management
    if controls.boost and state.battery > 2.0:
        state.boosting = True
        state.battery = max(0.0, state.battery - BATTERY_DRAIN_PER_SEC * dt)
    else:
        state.boosting = False
        state.battery = min(BATTERY_MAX, state.battery + BATTERY_REGEN_PER_SEC * dt)

    target_speed = BOOST_SPEED_KMH if state.boosting else BASE_SPEED_KMH
    state.speed_kmh += (target_speed - state.speed_kmh) * min(1.0, 6.0 * dt)
    state.pitch_deg = max(-24.0, min(24.0, (state.vy / MAX_VY) * 22.0))

    if state.invuln_timer > 0.0:
        state.invuln_timer = max(0.0, state.invuln_timer - dt)

    # Distance score scales with speed & combo
    state.score += (state.speed_kmh / 100.0) * state.combo * dt * 12.0


def aabb_overlap(
    ax: float,
    ay: float,
    aw: float,
    ah: float,
    bx: float,
    by: float,
    bw: float,
    bh: float,
) -> bool:
    """Return True if two center-anchored axis-aligned bounding boxes overlap."""
    return abs(ax - bx) * 2.0 < (aw + bw) and abs(ay - by) * 2.0 < (ah + bh)


def roadster_hits_box(state: RoadsterState, bx: float, by: float, bw: float, bh: float) -> bool:
    """Check collision using a slightly forgiving hitbox for responsive arcade feel."""
    return aabb_overlap(state.x, state.y, ROADSTER_W * 0.78, ROADSTER_H * 0.72, bx, by, bw, bh)
