# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Pure game rules for the one-row corridor (no pygame).

The corridor has ``CELLS`` cells. Pacman always moves in its current direction at
``HERO_SPEED`` cells/s and stops at the walls; the only control needed is *reverse* -
a single bit, which is what one blink provides. Dots fill the corridor, power pellets sit
at both ends. Ghosts patrol back and forth; touching one costs a life unless a pellet
made them frightened, in which case the ghost is eaten and returns to the ghost house.
Like in the arcade, ghosts wait in the house before their release time, and after being
caught Pacman respawns in the middle (keeping its direction) with a short invulnerability.
Eating all dots starts the next round (dots and pellets refill, ghosts get faster).
Surviving until ``time_limit_s``: won. No lives left: lost. With no direction yet, a
reverse starts Pacman away from the nearest ghost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

CELLS = 20
HERO_SPEED = 2.0
GHOST_SPEED = 0.6  # tuned so ~5 s blink cadence is playable (see tests)
FRIGHT_S = 6.0
LIVES = 3
TICK_S = 0.1
RESPAWN_GRACE_S = 2.0
HOUSE_S = 3.0
TIME_LIMIT_S = 60.0
ROUND_SPEEDUP = 0.15
ROUND_POINTS = 500
DOT_POINTS = 10
PELLET_POINTS = 50
GHOST_POINTS = 200
_HIT_DISTANCE = 0.6


class Command(Enum):
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    REVERSE = "reverse"


class Status(Enum):
    RUNNING = "running"
    WON = "won"
    LOST = "lost"


@dataclass
class Ghost:
    name: str
    x: float
    direction: int
    home: float
    eaten_count: int = 0
    release_s: float = 0.0
    """Game time at which the ghost leaves the house."""

    def active(self, time_s: float) -> bool:
        return time_s >= self.release_s


@dataclass(frozen=True)
class LogEntry:
    time_s: float
    event: str
    x: float


def _all_dots() -> set[int]:
    return set(range(1, CELLS - 1))


def _all_pellets() -> set[int]:
    return {0, CELLS - 1}


@dataclass
class GameState:
    hero_x: float = CELLS / 2
    direction: int = 0
    dots: set[int] = field(default_factory=_all_dots)
    pellets: set[int] = field(default_factory=_all_pellets)
    ghosts: list[Ghost] = field(
        default_factory=lambda: [Ghost("Blinky", 2.0, 1, 2.0, release_s=8.0)]
    )
    score: int = 0
    lives: int = LIVES
    fright_left_s: float = 0.0
    grace_left_s: float = 0.0
    time_s: float = 0.0
    time_limit_s: float = TIME_LIMIT_S
    round: int = 1
    status: Status = Status.RUNNING
    log: list[LogEntry] = field(default_factory=list)

    @property
    def hero_cell(self) -> int:
        return round(self.hero_x)

    @property
    def frightened(self) -> bool:
        return self.fright_left_s > 0

    def _event(self, event: str) -> None:
        self.log.append(LogEntry(round(self.time_s, 6), event, round(self.hero_x, 6)))

    def apply(self, command: Command) -> None:
        if self.status is not Status.RUNNING or command is Command.NONE:
            return
        new = {Command.LEFT: -1, Command.RIGHT: 1, Command.REVERSE: -self.direction}[command]
        if command is Command.REVERSE and self.direction == 0:
            new = self._away_from_nearest_ghost()
        if new != self.direction:
            self.direction = new
            self._event(f"turn:{'left' if new < 0 else 'right'}")

    def _away_from_nearest_ghost(self) -> int:
        active = [g for g in self.ghosts if g.active(self.time_s)]
        if not active:
            return 1 if self.hero_x < CELLS / 2 else -1
        nearest = min(active, key=lambda g: abs(g.x - self.hero_x))
        return 1 if nearest.x <= self.hero_x else -1

    @property
    def ghost_speed(self) -> float:
        return GHOST_SPEED * (1 + ROUND_SPEEDUP * (self.round - 1))

    def step(self, dt: float = TICK_S) -> None:
        if self.status is not Status.RUNNING:
            return
        # rounded so the clock does not drift away from tick multiples (0.1 is inexact)
        self.time_s = round(self.time_s + dt, 9)
        self.fright_left_s = max(0.0, self.fright_left_s - dt)
        self.grace_left_s = max(0.0, self.grace_left_s - dt)
        self._move_hero(dt)
        self._eat()
        self._move_ghosts(dt)
        self._collide()
        if self.status is not Status.RUNNING:
            return
        if not self.dots:
            self.round += 1
            self.score += ROUND_POINTS
            self.dots, self.pellets = _all_dots(), _all_pellets()
            self._event(f"round:{self.round}")
        if self.time_s >= self.time_limit_s - 1e-9:
            self.status = Status.WON
            self._event("won")

    def _move_hero(self, dt: float) -> None:
        self.hero_x = min(CELLS - 1.0, max(0.0, self.hero_x + self.direction * HERO_SPEED * dt))

    def _eat(self) -> None:
        cell = self.hero_cell
        if cell in self.dots:
            self.dots.discard(cell)
            self.score += DOT_POINTS
        if cell in self.pellets:
            self.pellets.discard(cell)
            self.score += PELLET_POINTS
            self.fright_left_s = FRIGHT_S
            self._event("pellet")

    def _move_ghosts(self, dt: float) -> None:
        for g in self.ghosts:
            if not g.active(self.time_s):
                continue
            g.x += g.direction * self.ghost_speed * dt
            if g.x <= 0 or g.x >= CELLS - 1:
                g.x = min(CELLS - 1.0, max(0.0, g.x))
                g.direction = -g.direction

    def _send_home(self, ghost: Ghost) -> None:
        ghost.x = ghost.home
        ghost.release_s = self.time_s + HOUSE_S

    def _collide(self) -> None:
        for g in self.ghosts:
            if not g.active(self.time_s) or abs(g.x - self.hero_x) >= _HIT_DISTANCE:
                continue
            if self.frightened:
                self.score += GHOST_POINTS
                g.eaten_count += 1
                self._send_home(g)
                self._event(f"ate:{g.name}")
            elif self.grace_left_s == 0:
                self.lives -= 1
                self._event(f"caught:{g.name}")
                self.hero_x = CELLS / 2
                self.grace_left_s = RESPAWN_GRACE_S
                for other in self.ghosts:
                    self._send_home(other)
                if self.lives <= 0:
                    self.status = Status.LOST
                    self._event("lost")
                return


def simulate(
    commands: dict[int, Command], max_ticks: int, state: GameState | None = None
) -> GameState:
    """Run the rules for ``max_ticks``; ``commands`` maps tick index -> command."""
    state = state or GameState()
    for tick in range(max_ticks):
        state.apply(commands.get(tick, Command.NONE))
        state.step()
        if state.status is not Status.RUNNING:
            break
    return state
