"""Obstacles, collectibles, parallax skyline, and particle pool."""

from __future__ import annotations

import random
from dataclasses import dataclass

from config import WINDOW_HEIGHT, WINDOW_WIDTH


@dataclass
class Obstacle:
    """Skyline hazard (security drone or laser gate)."""

    x: float
    y: float
    w: float
    h: float
    kind: str  # "drone" | "pillar"
    vy: float = 0.0


@dataclass
class Collectible:
    """Supercharger energy orb or Starman combo ring."""

    x: float
    y: float
    radius: float
    kind: str  # "orb" | "ring"
    collected: bool = False


@dataclass
class Particle:
    """Pooled thruster exhaust or spark particle."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    color: str


@dataclass
class Building:
    """Parallax cyber-skyline building silhouette."""

    x: float
    w: float
    h: float
    layer: int  # 0 = far, 1 = near
    color: str


class WorldManager:
    """Manages spawning, scrolling, and recycling of world entities."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.obstacles: list[Obstacle] = []
        self.collectibles: list[Collectible] = []
        self.particles: list[Particle] = []
        self.stars: list[tuple[float, float, float]] = [
            (
                self._rng.uniform(0, WINDOW_WIDTH),
                self._rng.uniform(10, WINDOW_HEIGHT * 0.65),
                self._rng.uniform(1.0, 2.5),
            )
            for _ in range(55)
        ]
        self.buildings: list[Building] = self._init_skyline()
        self._spawn_timer = 0.9
        self._collect_timer = 1.4

    def _init_skyline(self) -> list[Building]:
        items: list[Building] = []
        for layer, color, h_range in (
            (0, "#0e1738", (120, 260)),
            (1, "#13204a", (70, 180)),
        ):
            x = 0.0
            while x < WINDOW_WIDTH + 160:
                w = self._rng.uniform(46, 95)
                h = self._rng.uniform(*h_range)
                items.append(Building(x=x, w=w, h=h, layer=layer, color=color))
                x += w + self._rng.uniform(4, 18)
        return items

    def emit_thruster(self, x: float, y: float, boosting: bool) -> None:
        """Spawn capped thruster particles to maintain zero-lag 60 FPS."""
        if len(self.particles) > 90:
            return
        count = 2 if boosting else 1
        for _ in range(count):
            color = "#f8fafc" if boosting and self._rng.random() < 0.4 else "#38bdf8"
            self.particles.append(
                Particle(
                    x=x - 42.0,
                    y=y + self._rng.uniform(-4.0, 5.0),
                    vx=self._rng.uniform(-340.0, -190.0),
                    vy=self._rng.uniform(-35.0, 35.0),
                    life=0.28 if boosting else 0.18,
                    max_life=0.28 if boosting else 0.18,
                    size=self._rng.uniform(3.0, 6.5 if boosting else 4.0),
                    color=color,
                )
            )

    def step(self, dt: float, scroll_px_per_sec: float) -> None:
        """Advance obstacles, collectibles, skyline, and particles."""
        # Scroll stars
        for i, (sx, sy, sz) in enumerate(self.stars):
            nx = sx - scroll_px_per_sec * 0.06 * dt
            if nx < -4:
                nx = WINDOW_WIDTH + 4
                sy = self._rng.uniform(10, WINDOW_HEIGHT * 0.65)
            self.stars[i] = (nx, sy, sz)

        # Scroll skyline buildings
        for b in self.buildings:
            factor = 0.18 if b.layer == 0 else 0.36
            b.x -= scroll_px_per_sec * factor * dt
            if b.x + b.w < -10:
                b.x = WINDOW_WIDTH + self._rng.uniform(10, 80)

        # Spawn obstacles
        self._spawn_timer -= dt
        if self._spawn_timer <= 0.0:
            self._spawn_timer = self._rng.uniform(0.65, 1.35)
            if self._rng.random() < 0.65:
                self.obstacles.append(
                    Obstacle(
                        x=WINDOW_WIDTH + 60.0,
                        y=self._rng.uniform(75.0, WINDOW_HEIGHT - 95.0),
                        w=44.0,
                        h=26.0,
                        kind="drone",
                        vy=self._rng.uniform(-75.0, 75.0),
                    )
                )
            else:
                from_top = self._rng.random() < 0.5
                h = self._rng.uniform(130.0, 210.0)
                y = h * 0.5 if from_top else WINDOW_HEIGHT - h * 0.5 - 30.0
                self.obstacles.append(
                    Obstacle(x=WINDOW_WIDTH + 60.0, y=y, w=32.0, h=h, kind="pillar")
                )

        # Spawn collectibles
        self._collect_timer -= dt
        if self._collect_timer <= 0.0:
            self._collect_timer = self._rng.uniform(1.1, 2.2)
            kind = "orb" if self._rng.random() < 0.55 else "ring"
            self.collectibles.append(
                Collectible(
                    x=WINDOW_WIDTH + 50.0,
                    y=self._rng.uniform(80.0, WINDOW_HEIGHT - 90.0),
                    radius=16.0 if kind == "orb" else 22.0,
                    kind=kind,
                )
            )

        # Move & cull obstacles
        kept_obs: list[Obstacle] = []
        for obs in self.obstacles:
            obs.x -= scroll_px_per_sec * dt
            if obs.kind == "drone":
                obs.y += obs.vy * dt
                if obs.y < 60.0 or obs.y > WINDOW_HEIGHT - 70.0:
                    obs.vy = -obs.vy
            if obs.x + obs.w > -60.0:
                kept_obs.append(obs)
        self.obstacles = kept_obs

        # Move & cull collectibles
        kept_col: list[Collectible] = []
        for col in self.collectibles:
            col.x -= scroll_px_per_sec * dt
            if not col.collected and col.x + col.radius > -40.0:
                kept_col.append(col)
        self.collectibles = kept_col

        # Update & cull particles
        kept_part: list[Particle] = []
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
            if p.life > 0.0:
                kept_part.append(p)
        self.particles = kept_part
