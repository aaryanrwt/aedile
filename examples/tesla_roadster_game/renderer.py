"""High-contrast 60 FPS Canvas renderer for Tesla Roadster Skyline."""

from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING

from config import (
    CAR_BODY,
    CAR_GLASS,
    CAR_TRIM,
    GRID_COLOR,
    OBSTACLE_RED,
    ORB_GREEN,
    RING_GOLD,
    THRUSTER_CORE,
    THRUSTER_CYAN,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

if TYPE_CHECKING:
    from entities import WorldManager
    from physics import RoadsterState


def _rotate_points(
    pts: list[tuple[float, float]], cx: float, cy: float, angle_deg: float
) -> list[float]:
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    flat: list[float] = []
    for px, py in pts:
        flat.append(cx + px * cos_a - py * sin_a)
        flat.append(cy + px * sin_a + py * cos_a)
    return flat


def render_frame(
    canvas: tk.Canvas,
    state: RoadsterState,
    world: WorldManager,
    fps: float,
    high_score: int,
    paused: bool,
    scroll_phase: float,
) -> None:
    """Clear and redraw the full game scene cleanly without object leaks."""
    canvas.delete("all")

    # 1. Starfield
    for sx, sy, sz in world.stars:
        canvas.create_oval(sx, sy, sx + sz, sy + sz, fill="#cbd5e1", outline="")

    # 2. Parallax Cyber-Skyline
    floor_y = WINDOW_HEIGHT - 30
    for b in world.buildings:
        canvas.create_rectangle(
            b.x, floor_y - b.h, b.x + b.w, floor_y, fill=b.color, outline="#1e3a8a"
        )

    # 3. Synthwave Horizon Grid
    canvas.create_rectangle(0, floor_y, WINDOW_WIDTH, WINDOW_HEIGHT, fill="#090f24", outline="")
    canvas.create_line(0, floor_y, WINDOW_WIDTH, floor_y, fill="#38bdf8", width=2)
    step = 60
    offset = scroll_phase % step
    for gx in range(-step, WINDOW_WIDTH + step, step):
        x_top = gx - offset
        canvas.create_line(x_top, floor_y, x_top - 45, WINDOW_HEIGHT, fill=GRID_COLOR, width=1)

    # 4. Thruster Particles
    for p in world.particles:
        alpha_ratio = max(0.2, p.life / p.max_life)
        r = p.size * alpha_ratio
        canvas.create_oval(p.x - r, p.y - r, p.x + r, p.y + r, fill=p.color, outline="")

    # 5. Collectibles
    for col in world.collectibles:
        if col.kind == "orb":
            r = col.radius
            canvas.create_oval(
                col.x - r,
                col.y - r,
                col.x + r,
                col.y + r,
                fill=ORB_GREEN,
                outline="#ecfdf5",
                width=2,
            )
            canvas.create_text(
                col.x, col.y, text="⚡", fill="#052e16", font=("Segoe UI", 10, "bold")
            )
        else:
            r = col.radius
            canvas.create_oval(
                col.x - r, col.y - r, col.x + r, col.y + r, fill="", outline=RING_GOLD, width=4
            )

    # 6. Obstacles
    for obs in world.obstacles:
        x0, y0 = obs.x - obs.w * 0.5, obs.y - obs.h * 0.5
        x1, y1 = obs.x + obs.w * 0.5, obs.y + obs.h * 0.5
        if obs.kind == "drone":
            canvas.create_rectangle(x0, y0, x1, y1, fill="#1f2937", outline=OBSTACLE_RED, width=2)
            canvas.create_oval(
                obs.x - 6, obs.y - 6, obs.x + 6, obs.y + 6, fill=OBSTACLE_RED, outline="#fecdd3"
            )
        else:
            canvas.create_rectangle(x0, y0, x1, y1, fill="#3b0712", outline=OBSTACLE_RED, width=2)
            canvas.create_line(obs.x, y0 + 4, obs.x, y1 - 4, fill="#fb7185", width=3)

    # 7. Flying Tesla Roadster
    _draw_roadster(canvas, state)

    # 8. HUD Overlay
    _draw_hud(canvas, state, fps, high_score, paused)


def _draw_roadster(canvas: tk.Canvas, state: RoadsterState) -> None:
    cx, cy, ang = state.x, state.y, state.pitch_deg

    # SpaceX cold-gas thruster flame
    if state.alive:
        flame_len = 36.0 if state.boosting else 18.0
        flame_pts = _rotate_points(
            [(-42, -5), (-42 - flame_len, 0), (-42, 5)],
            cx,
            cy,
            ang,
        )
        canvas.create_polygon(flame_pts, fill=THRUSTER_CYAN, outline="")
        core_pts = _rotate_points(
            [(-40, -2.5), (-40 - flame_len * 0.55, 0), (-40, 2.5)],
            cx,
            cy,
            ang,
        )
        canvas.create_polygon(core_pts, fill=THRUSTER_CORE, outline="")

    # Sleek Roadster chassis silhouette
    body_pts = _rotate_points(
        [(-42, 6), (-36, -6), (-14, -9), (10, -13), (34, -4), (44, 2), (40, 9), (-38, 10)],
        cx,
        cy,
        ang,
    )
    canvas.create_polygon(body_pts, fill=CAR_BODY, outline=CAR_TRIM, width=1.5)

    # Aero glass canopy
    glass_pts = _rotate_points([(-12, -8), (8, -12), (24, -4), (-4, -3)], cx, cy, ang)
    canvas.create_polygon(glass_pts, fill=CAR_GLASS, outline="#e0f2fe")

    # Retracted hover-wheel pods with cyan underglow
    for wx in (-24.0, 24.0):
        w_pts = _rotate_points([(wx - 6, 8), (wx + 6, 8), (wx + 5, 13), (wx - 5, 13)], cx, cy, ang)
        canvas.create_polygon(w_pts, fill="#0f172a", outline=THRUSTER_CYAN, width=1.5)


def _draw_hud(
    canvas: tk.Canvas, state: RoadsterState, fps: float, high_score: int, paused: bool
) -> None:
    alt_m = int((WINDOW_HEIGHT - 56 - state.y) * 2.4)
    mach = state.speed_kmh / 1235.0
    canvas.create_text(
        20,
        22,
        anchor="w",
        text=f"SCORE {int(state.score):,}   |   BEST {high_score:,}   |   COMBO x{state.combo}",
        fill="#f8fafc",
        font=("Consolas", 13, "bold"),
    )
    canvas.create_text(
        20,
        46,
        anchor="w",
        text=f"SPEED {int(state.speed_kmh)} km/h (M {mach:.2f})   |   ALT {alt_m} m   |   {fps:.0f} FPS",
        fill="#38bdf8",
        font=("Consolas", 11),
    )

    # Battery gauge
    bar_x, bar_y, bar_w, bar_h = WINDOW_WIDTH - 220, 18, 190, 16
    canvas.create_rectangle(
        bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, fill="#0f172a", outline="#475569"
    )
    fill_w = max(0.0, (state.battery / 100.0) * (bar_w - 4))
    bar_color = "#34d399" if state.battery > 30 else "#f43f5e"
    canvas.create_rectangle(
        bar_x + 2, bar_y + 2, bar_x + 2 + fill_w, bar_y + bar_h - 2, fill=bar_color, outline=""
    )
    canvas.create_text(
        bar_x - 10,
        bar_y + 8,
        anchor="e",
        text="SPACEX BOOST",
        fill="#cbd5e1",
        font=("Consolas", 10, "bold"),
    )

    canvas.create_text(
        WINDOW_WIDTH - 20,
        WINDOW_HEIGHT - 14,
        anchor="e",
        text="Controls: W/Up/Space=Thrust  S/Down=Dive  A/D=Dash  Shift=Boost  P=Pause  R=Restart",
        fill="#94a3b8",
        font=("Consolas", 9),
    )

    if paused and state.alive:
        canvas.create_rectangle(
            WINDOW_WIDTH / 2 - 160,
            WINDOW_HEIGHT / 2 - 45,
            WINDOW_WIDTH / 2 + 160,
            WINDOW_HEIGHT / 2 + 45,
            fill="#020617",
            outline="#38bdf8",
            width=2,
        )
        canvas.create_text(
            WINDOW_WIDTH / 2,
            WINDOW_HEIGHT / 2,
            text="PAUSED — Press P to Resume",
            fill="#f8fafc",
            font=("Segoe UI", 16, "bold"),
        )

    if not state.alive:
        canvas.create_rectangle(
            WINDOW_WIDTH / 2 - 220,
            WINDOW_HEIGHT / 2 - 70,
            WINDOW_WIDTH / 2 + 220,
            WINDOW_HEIGHT / 2 + 70,
            fill="#020617",
            outline="#f43f5e",
            width=2,
        )
        canvas.create_text(
            WINDOW_WIDTH / 2,
            WINDOW_HEIGHT / 2 - 18,
            text=f"FLIGHT TERMINATED — SCORE {int(state.score):,}",
            fill="#fda4af",
            font=("Segoe UI", 16, "bold"),
        )
        canvas.create_text(
            WINDOW_WIDTH / 2,
            WINDOW_HEIGHT / 2 + 22,
            text="Press R to Launch New Roadster",
            fill="#f8fafc",
            font=("Segoe UI", 12),
        )
