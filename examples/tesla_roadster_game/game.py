"""Main Tkinter game loop controller for Tesla Roadster Skyline."""

from __future__ import annotations

import time
import tkinter as tk

from config import BG_SKY_TOP, FRAME_MS, WINDOW_HEIGHT, WINDOW_WIDTH
from entities import WorldManager
from physics import InputState, RoadsterState, aabb_overlap, roadster_hits_box, step_roadster
from renderer import render_frame


class TeslaRoadsterApp:
    """Interactive 60 FPS Tesla Roadster Flying Car game."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tesla Roadster: Skyline Flight")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            root, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, bg=BG_SKY_TOP, highlightthickness=0
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.paused = False
        self.high_score = 0
        self.scroll_phase = 0.0
        self.state = RoadsterState()
        self.world = WorldManager()
        self._last_t = time.perf_counter()
        self._fps = 60.0

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
        """Reset flight state and world for an instant restart."""
        self.high_score = max(self.high_score, int(self.state.score))
        self.state = RoadsterState()
        self.world = WorldManager()
        self.paused = False

    def _read_controls(self) -> InputState:
        return InputState(
            thrust_up=bool(self.keys & {"w", "up", "space"}),
            dive_down=bool(self.keys & {"s", "down"}),
            move_left=bool(self.keys & {"a", "left"}),
            move_right=bool(self.keys & {"d", "right"}),
            boost=bool(self.keys & {"shift_l", "shift_r"}),
        )

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = max(0.001, min(0.05, now - self._last_t))
        self._last_t = now
        self._fps = self._fps * 0.9 + (1.0 / dt) * 0.1

        if not self.paused and self.state.alive:
            controls = self._read_controls()
            step_roadster(self.state, controls, dt)
            scroll_px = self.state.speed_kmh * 1.15
            self.scroll_phase += scroll_px * dt
            self.world.emit_thruster(self.state.x, self.state.y, self.state.boosting)
            self.world.step(dt, scroll_px)

            # Check collectibles
            for col in self.world.collectibles:
                if not col.collected and aabb_overlap(
                    self.state.x,
                    self.state.y,
                    70.0,
                    26.0,
                    col.x,
                    col.y,
                    col.radius * 2,
                    col.radius * 2,
                ):
                    col.collected = True
                    if col.kind == "orb":
                        self.state.battery = min(100.0, self.state.battery + 30.0)
                        self.state.score += 120.0 * self.state.combo
                    else:
                        self.state.combo = min(10, self.state.combo + 1)
                        self.state.score += 200.0 * self.state.combo

            # Check obstacle collisions
            if self.state.invuln_timer <= 0.0:
                for obs in self.world.obstacles:
                    if roadster_hits_box(self.state, obs.x, obs.y, obs.w, obs.h):
                        self.state.alive = False
                        self.high_score = max(self.high_score, int(self.state.score))
                        break

        render_frame(
            self.canvas,
            self.state,
            self.world,
            self._fps,
            max(self.high_score, int(self.state.score)),
            self.paused,
            self.scroll_phase,
        )
        self.root.after(FRAME_MS, self._tick)


def launch() -> None:
    """Create window and start main loop."""
    root = tk.Tk()
    TeslaRoadsterApp(root)
    root.mainloop()
