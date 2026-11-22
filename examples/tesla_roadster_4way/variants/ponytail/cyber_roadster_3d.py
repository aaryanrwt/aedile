"""High-graphics 3D-perspective Cyber-Roadster flying car engine (Tkinter Canvas)."""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass

WIN_W = 1180
WIN_H = 680
HORIZON_Y = 235
TARGET_FPS = 60
FRAME_MS = 1000 // TARGET_FPS


@dataclass
class CyberRoadsterState:
    """3D highway & flight state for the faceted Cyber-Roadster."""

    lane_x: float = 0.0  # -1.0 (left) to +1.0 (right)
    vx: float = 0.0
    hover_z: float = 0.0  # 0.0 = on road, >0 = flying
    vz: float = 0.0
    speed_kmh: float = 290.0
    battery: float = 100.0
    boosting: bool = False
    score: float = 0.0
    combo: int = 1
    wheel_phase: float = 0.0
    road_z: float = 0.0
    alive: bool = True


@dataclass
class RoadEntity:
    """3D-projected traffic barrier, drone, or supercharger orb."""

    lane_x: float
    z: float  # 1.0 (near camera) .. 45.0 (horizon)
    y_height: float  # 0.0 = road level, >0 = airborne
    kind: str  # "blocker" | "drone" | "orb"


def _default_ai_step(state: CyberRoadsterState, dt: float) -> None:
    """Default telemetry & combo multiplier hook (overridden by qwen3:4b AI module)."""
    if state.boosting and state.hover_z > 0.2:
        state.score += dt * 45.0 * state.combo


class CyberRoadster3DApp:
    """60 FPS 3D-perspective Cyber-Roadster game window."""

    def __init__(
        self,
        root: tk.Tk,
        variant_label: str,
        ai_hook: Callable[[CyberRoadsterState, float], None] | None = None,
    ) -> None:
        self.root = root
        self.variant_label = variant_label
        self.ai_hook = ai_hook or _default_ai_step
        self.root.title(f"Tesla Cyber-Roadster 3D — [{variant_label}]")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg="#060913", highlightthickness=0)
        self.canvas.pack()

        self.keys: set[str] = set()
        self.paused = False
        self.high_score = 0
        self.state = CyberRoadsterState()
        self.rng = random.Random(42)
        self.entities: list[RoadEntity] = []
        self._spawn_cd = 0.8
        self._last_t = time.perf_counter()
        self._fps = 60.0
        self._stars = [
            (
                self.rng.uniform(0, WIN_W),
                self.rng.uniform(8, HORIZON_Y - 20),
                self.rng.uniform(1.0, 2.2),
            )
            for _ in range(55)
        ]

        self.root.bind("<KeyPress>", self._on_key_down)
        self.root.bind("<KeyRelease>", self._on_key_up)
        self._tick()

    def _on_key_down(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        sym = event.keysym.lower()
        self.keys.add(sym)
        if sym == "p" and self.state.alive:
            self.paused = not self.paused
        elif sym == "r":
            self.reset()

    def _on_key_up(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self.keys.discard(event.keysym.lower())

    def reset(self) -> None:
        """Reset 3D highway run."""
        self.high_score = max(self.high_score, int(self.state.score))
        self.state = CyberRoadsterState()
        self.entities.clear()
        self.paused = False

    def step_simulation(self, dt: float) -> None:
        """Advance 3D physics, entities, and collisions by dt seconds."""
        st = self.state
        if not st.alive or self.paused:
            return
        dt = min(max(dt, 0.001), 0.05)

        # Steering
        steer = 0.0
        if self.keys & {"a", "left"}:
            steer -= 2.4
        if self.keys & {"d", "right"}:
            steer += 2.4
        st.vx += (steer - st.vx * 5.0) * dt * 3.2
        st.lane_x = max(-0.92, min(0.92, st.lane_x + st.vx * dt))

        # SpaceX vertical hover/flight
        az = -14.5
        if self.keys & {"w", "up", "space"}:
            az += 31.0
        if self.keys & {"s", "down"}:
            az -= 18.0
        st.vz = max(-9.0, min(9.0, st.vz + az * dt))
        st.hover_z = max(0.0, min(3.8, st.hover_z + st.vz * dt))
        if st.hover_z == 0.0 and st.vz < 0.0:
            st.vz = 0.0

        # Boost & speed
        want_boost = bool(self.keys & {"shift_l", "shift_r"})
        if want_boost and st.battery > 2.0:
            st.boosting = True
            st.battery = max(0.0, st.battery - 26.0 * dt)
        else:
            st.boosting = False
            st.battery = min(100.0, st.battery + 11.0 * dt)

        target_kmh = 640.0 if st.boosting else 300.0
        st.speed_kmh += (target_kmh - st.speed_kmh) * min(1.0, 5.5 * dt)
        world_v = st.speed_kmh * 0.075
        st.road_z += world_v * dt
        st.wheel_phase += world_v * dt * 1.4
        st.score += (st.speed_kmh / 100.0) * st.combo * dt * 15.0

        self.ai_hook(st, dt)

        # Spawn 3D traffic & supercharger orbs
        self._spawn_cd -= dt
        if self._spawn_cd <= 0.0:
            self._spawn_cd = self.rng.uniform(0.45, 0.95)
            roll = self.rng.random()
            if roll < 0.35:
                kind, yh = "orb", self.rng.uniform(0.0, 2.2)
            elif roll < 0.7:
                kind, yh = "blocker", 0.0
            else:
                kind, yh = "drone", self.rng.uniform(1.0, 2.8)
            self.entities.append(
                RoadEntity(
                    lane_x=self.rng.uniform(-0.78, 0.78),
                    z=44.0,
                    y_height=yh,
                    kind=kind,
                )
            )

        # Move & collide
        kept: list[RoadEntity] = []
        for ent in self.entities:
            ent.z -= world_v * dt
            if 1.4 <= ent.z <= 2.3:
                dx = abs(ent.lane_x - st.lane_x)
                dz = abs(ent.y_height - st.hover_z)
                if ent.kind == "orb" and dx < 0.32 and dz < 1.1:
                    st.battery = min(100.0, st.battery + 28.0)
                    st.combo = min(10, st.combo + 1)
                    st.score += 180.0 * st.combo
                    continue
                if ent.kind in {"blocker", "drone"} and dx < 0.24 and dz < 0.78:
                    st.alive = False
                    self.high_score = max(self.high_score, int(st.score))
            if ent.z > 0.8:
                kept.append(ent)
        self.entities = kept

    def _project(self, lane_x: float, z: float, height: float = 0.0) -> tuple[float, float, float]:
        """Project 3D road coordinates (lane_x, z, height) to 2D screen (sx, sy, scale)."""
        scale = 1.0 / max(0.4, z)
        cam_x = self.state.lane_x * 160.0
        vp_x = WIN_W * 0.5 - cam_x * 0.35
        sx = vp_x + (lane_x * 520.0 - cam_x * 0.65) * scale * 2.2
        sy = HORIZON_Y + (WIN_H - HORIZON_Y) * scale * 1.45 - height * 165.0 * scale
        return sx, sy, scale

    def render(self) -> None:
        """Render 3D sky, perspective road, pylons, entities, Cyber-Roadster, and HUD."""
        c = self.canvas
        c.delete("all")
        st = self.state

        # 1. Sky gradient bands & stars
        c.create_rectangle(0, 0, WIN_W, HORIZON_Y, fill="#090d1c", outline="")
        c.create_rectangle(0, HORIZON_Y - 55, WIN_W, HORIZON_Y, fill="#111936", outline="")
        for sx, sy, sz in self._stars:
            c.create_oval(sx, sy, sx + sz, sy + sz, fill="#cbd5e1", outline="")

        # Distant neon horizon glow
        c.create_line(0, HORIZON_Y, WIN_W, HORIZON_Y, fill="#38bdf8", width=2)

        # 2. Ground plane & 3D perspective highway strips
        c.create_rectangle(0, HORIZON_Y, WIN_W, WIN_H, fill="#070b17", outline="")
        z_edges = [44.0, 26.0, 16.0, 10.5, 7.0, 4.8, 3.3, 2.2, 1.4, 0.8]
        phase_shift = st.road_z % 2.0
        for idx in range(len(z_edges) - 1):
            z_far = z_edges[idx]
            z_near = z_edges[idx + 1]
            lx0, y0, _ = self._project(-1.05, z_far)
            rx0, _, _ = self._project(1.05, z_far)
            lx1, y1, _ = self._project(-1.05, z_near)
            rx1, _, _ = self._project(1.05, z_near)
            band = (idx + int(st.road_z)) % 2 == 0
            asphalt = "#111827" if band else "#0f172a"
            c.create_polygon(lx0, y0, rx0, y0, rx1, y1, lx1, y1, fill=asphalt, outline="")
            # Glowing road shoulders
            c.create_line(lx0, y0, lx1, y1, fill="#38bdf8", width=2)
            c.create_line(rx0, y0, rx1, y1, fill="#38bdf8", width=2)
            # Dashed lane dividers
            if (idx + int(phase_shift)) % 2 == 0:
                for lane in (-0.35, 0.35):
                    mx0, _, _ = self._project(lane, z_far)
                    mx1, _, _ = self._project(lane, z_near)
                    c.create_line(mx0, y0, mx1, y1, fill="#64748b", width=2)

        # 3. 3D Roadside neon pylons
        for i in range(1, 10):
            pz = ((i * 4.5 - (st.road_z % 4.5)) % 40.0) + 1.2
            for side in (-1.32, 1.32):
                px, py, sc = self._project(side, pz)
                ph = max(4.0, 170.0 * sc)
                c.create_line(px, py, px, py - ph, fill="#1e3a8a", width=max(1, int(4 * sc)))
                c.create_oval(
                    px - 3 * sc,
                    py - ph - 3 * sc,
                    px + 3 * sc,
                    py - ph + 3 * sc,
                    fill="#38bdf8",
                    outline="",
                )

        # 4. 3D Entities (sorted far -> near)
        for ent in sorted(self.entities, key=lambda e: e.z, reverse=True):
            ex, ey, sc = self._project(ent.lane_x, ent.z, ent.y_height)
            sz = max(4.0, 72.0 * sc)
            if ent.kind == "orb":
                c.create_oval(
                    ex - sz * 0.55,
                    ey - sz * 0.55,
                    ex + sz * 0.55,
                    ey + sz * 0.55,
                    fill="#34d399",
                    outline="#ecfdf5",
                    width=2,
                )
            elif ent.kind == "drone":
                c.create_polygon(
                    ex - sz,
                    ey,
                    ex,
                    ey - sz * 0.5,
                    ex + sz,
                    ey,
                    ex,
                    ey + sz * 0.5,
                    fill="#1f2937",
                    outline="#f43f5e",
                    width=2,
                )
            else:
                c.create_rectangle(
                    ex - sz * 0.9,
                    ey - sz * 0.85,
                    ex + sz * 0.9,
                    ey,
                    fill="#450a0a",
                    outline="#fb7185",
                    width=2,
                )

        # 5. Faceted Pearl-White Cyber-Roadster (matching reference aesthetic)
        self._draw_cyber_roadster()

        # 6. Telemetry HUD
        self._draw_hud()

    def _draw_cyber_roadster(self) -> None:
        c = self.canvas
        st = self.state
        cx = WIN_W * 0.5 + st.lane_x * 235.0
        ground_y = WIN_H - 96.0
        cy = ground_y - st.hover_z * 58.0
        tilt = st.vx * 6.5

        # Ground shadow (shrinks when flying higher)
        sh_scale = max(0.45, 1.0 - st.hover_z * 0.14)
        c.create_oval(
            cx - 108 * sh_scale,
            ground_y + 18,
            cx + 108 * sh_scale,
            ground_y + 42,
            fill="#02040a",
            outline="",
        )

        # 5-Spoke Black Aero Wheels (visible on lower flanks)
        for wx_off in (-72.0, 72.0):
            wx = cx + wx_off
            wy = cy + 20.0 + (tilt * 0.15 if wx_off > 0 else -tilt * 0.15)
            c.create_oval(
                wx - 22, wy - 18, wx + 22, wy + 18, fill="#0f172a", outline="#475569", width=2
            )
            for sp in range(5):
                ang = st.wheel_phase + sp * (2.0 * math.pi / 5.0)
                c.create_line(
                    wx,
                    wy,
                    wx + math.cos(ang) * 16,
                    wy + math.sin(ang) * 13,
                    fill="#94a3b8",
                    width=2,
                )

        # Lower carbon diffuser & side skirt
        c.create_polygon(
            cx - 102,
            cy + 22,
            cx - 86,
            cy + 28,
            cx + 86,
            cy + 28,
            cx + 102,
            cy + 20,
            fill="#090d16",
            outline="#1e293b",
        )

        # Pearl-White Faceted Wedge Body (3D shaded polygons)
        c.create_polygon(
            cx - 104,
            cy + 12,
            cx - 94,
            cy - 12,
            cx - 42,
            cy - 22,
            cx + 42,
            cy - 22,
            cx + 94,
            cy - 12,
            cx + 104,
            cy + 12,
            cx + 82,
            cy + 20,
            cx - 82,
            cy + 20,
            fill="#f1f5f9",
            outline="#cbd5e1",
            width=1.5,
        )
        # Side crease highlights
        c.create_polygon(
            cx - 94,
            cy - 10,
            cx - 44,
            cy - 20,
            cx - 32,
            cy + 6,
            cx - 96,
            cy + 10,
            fill="#e2e8f0",
            outline="",
        )
        c.create_polygon(
            cx + 94,
            cy - 10,
            cx + 44,
            cy - 20,
            cx + 32,
            cy + 6,
            cx + 96,
            cy + 10,
            fill="#cbd5e1",
            outline="",
        )

        # Angular Smoked-Glass Canopy + Specular Reflection
        c.create_polygon(
            cx - 56,
            cy - 16,
            cx - 28,
            cy - 38,
            cx + 28,
            cy - 38,
            cx + 56,
            cy - 16,
            cx + 42,
            cy - 4,
            cx - 42,
            cy - 4,
            fill="#090d16",
            outline="#94a3b8",
            width=1.5,
        )
        c.create_polygon(
            cx - 22,
            cy - 36,
            cx + 14,
            cy - 36,
            cx + 28,
            cy - 20,
            cx - 8,
            cy - 20,
            fill="#334155",
            outline="",
        )

        # Full-Width Matte-White Rear Wing Spoiler
        c.create_polygon(
            cx - 88,
            cy - 28,
            cx + 88,
            cy - 28,
            cx + 82,
            cy - 20,
            cx - 82,
            cy - 20,
            fill="#f8fafc",
            outline="#94a3b8",
            width=1.5,
        )
        c.create_line(cx - 64, cy - 20, cx - 64, cy - 10, fill="#cbd5e1", width=3)
        c.create_line(cx + 64, cy - 20, cx + 64, cy - 10, fill="#cbd5e1", width=3)

        # Full-Width Red LED Tail Lightbar
        c.create_line(cx - 86, cy - 6, cx + 86, cy - 6, fill="#ef4444", width=4)
        c.create_line(cx - 80, cy - 6, cx + 80, cy - 6, fill="#fecaca", width=1.5)

        # 6-Nozzle SpaceX Cold-Gas Rear Thruster Bank
        c.create_rectangle(cx - 56, cy + 6, cx + 56, cy + 24, fill="#020617", outline="#334155")
        for idx in range(6):
            nx = cx - 42 + idx * 16.8
            ny = cy + 15
            c.create_oval(nx - 5, ny - 5, nx + 5, ny + 5, fill="#1e293b", outline="#94a3b8")
            if st.boosting or st.hover_z > 0.15:
                flame_r = 14.0 if st.boosting else 7.5
                c.create_polygon(
                    nx - 4, ny + 2, nx + 4, ny + 2, nx, ny + 2 + flame_r, fill="#38bdf8", outline=""
                )
                c.create_oval(nx - 2, ny - 1, nx + 2, ny + 3, fill="#f8fafc", outline="")

    def _draw_hud(self) -> None:
        c = self.canvas
        st = self.state
        alt_m = int(st.hover_z * 45)
        c.create_text(
            22,
            22,
            anchor="w",
            text=f"[{self.variant_label}]   SCORE {int(st.score):,}   |   BEST {self.high_score:,}   |   COMBO x{st.combo}",
            fill="#f8fafc",
            font=("Consolas", 12, "bold"),
        )
        c.create_text(
            22,
            46,
            anchor="w",
            text=f"SPEED {int(st.speed_kmh)} km/h   |   ALT {alt_m} m   |   {self._fps:.0f} FPS",
            fill="#38bdf8",
            font=("Consolas", 11),
        )
        bar_x, bar_y, bar_w, bar_h = WIN_W - 220, 18, 190, 16
        c.create_rectangle(
            bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, fill="#0f172a", outline="#475569"
        )
        fw = max(0.0, (st.battery / 100.0) * (bar_w - 4))
        c.create_rectangle(
            bar_x + 2, bar_y + 2, bar_x + 2 + fw, bar_y + bar_h - 2, fill="#34d399", outline=""
        )
        c.create_text(
            bar_x - 10,
            bar_y + 8,
            anchor="e",
            text="SPACEX BOOST",
            fill="#cbd5e1",
            font=("Consolas", 10, "bold"),
        )
        c.create_text(
            WIN_W - 22,
            WIN_H - 14,
            anchor="e",
            text="A/D=Steer  W/Space=Fly  S=Land  Shift=Boost  P=Pause  R=Restart",
            fill="#94a3b8",
            font=("Consolas", 9),
        )
        if not st.alive:
            c.create_rectangle(
                WIN_W / 2 - 220,
                WIN_H / 2 - 55,
                WIN_W / 2 + 220,
                WIN_H / 2 + 55,
                fill="#020617",
                outline="#f43f5e",
                width=2,
            )
            c.create_text(
                WIN_W / 2,
                WIN_H / 2 - 14,
                text=f"CRASHED — SCORE {int(st.score):,}",
                fill="#fda4af",
                font=("Segoe UI", 16, "bold"),
            )
            c.create_text(
                WIN_W / 2,
                WIN_H / 2 + 20,
                text="Press R to Relaunch Cyber-Roadster",
                fill="#f8fafc",
                font=("Segoe UI", 12),
            )

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = max(0.001, min(0.05, now - self._last_t))
        self._last_t = now
        self._fps = self._fps * 0.9 + (1.0 / dt) * 0.1
        self.step_simulation(dt)
        self.render()
        self.root.after(FRAME_MS, self._tick)


def run_game(
    variant_label: str, ai_hook: Callable[[CyberRoadsterState, float], None] | None = None
) -> None:
    """Launch Cyber-Roadster 3D window."""
    root = tk.Tk()
    CyberRoadster3DApp(root, variant_label=variant_label, ai_hook=ai_hook)
    root.mainloop()
