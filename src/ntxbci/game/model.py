# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Pure game rules for the one-row corridor (no pygame).

The corridor has ``CELLS`` cells. Pacman always moves in its current direction at
``HERO_SPEED`` cells/s and stops at the walls; the only control needed is *reverse* -
a single bit, which is what one blink provides. Dots fill the corridor, power pellets sit
at both ends. Ghosts patrol back and forth; touching one costs a life unless a pellet
made them frightened, in which case the ghost is eaten and respawns. All dots eaten: won.
No lives left: lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

CELLS = 20
HERO_SPEED = 2.0
GHOST_SPEED = 1.0
FRIGHT_S = 6.0
LIVES = 3
TICK_S = 0.1
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


@dataclass(frozen=True)
class LogEntry:
    time_s: float
    event: str
    x: float


@dataclass
class GameState:
    hero_x: float = CELLS / 2
    direction: int = 1
    dots: set[int] = field(default_factory=lambda: set(range(1, CELLS - 1)))
    pellets: set[int] = field(default_factory=lambda: {0, CELLS - 1})
    ghosts: list[Ghost] = field(
        default_factory=lambda: [Ghost("Blinky", 2.0, 1, 2.0), Ghost("Clyde", 17.0, -1, 17.0)]
    )
    score: int = 0
    lives: int = LIVES
    fright_left_s: float = 0.0
    time_s: float = 0.0
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
            new = 1 if self.hero_x < CELLS / 2 else -1
        if new != self.direction:
            self.direction = new
            self._event(f"turn:{'left' if new < 0 else 'right'}")

    def step(self, dt: float = TICK_S) -> None:
        if self.status is not Status.RUNNING:
            return
        self.time_s += dt
        self.fright_left_s = max(0.0, self.fright_left_s - dt)
        self._move_hero(dt)
        self._eat()
        self._move_ghosts(dt)
        self._collide()
        if not self.dots and self.status is Status.RUNNING:
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
            g.x += g.direction * GHOST_SPEED * dt
            if g.x <= 0 or g.x >= CELLS - 1:
                g.x = min(CELLS - 1.0, max(0.0, g.x))
                g.direction = -g.direction

    def _collide(self) -> None:
        for g in self.ghosts:
            if abs(g.x - self.hero_x) >= _HIT_DISTANCE:
                continue
            if self.frightened:
                self.score += GHOST_POINTS
                g.eaten_count += 1
                g.x = g.home
                self._event(f"ate:{g.name}")
            else:
                self.lives -= 1
                self._event(f"caught:{g.name}")
                self.hero_x, self.direction = CELLS / 2, 0
                for other in self.ghosts:
                    other.x = other.home
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
