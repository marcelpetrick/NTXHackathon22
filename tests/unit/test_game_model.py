# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import random

import pytest

from ntxbci.game import model
from ntxbci.game.controllers import ScriptedController
from ntxbci.game.model import Command, GameState, Ghost, Status


def _empty(**kwargs: object) -> GameState:
    return GameState(ghosts=[], **kwargs)  # type: ignore[arg-type]


def _play(blinks: list[float], limit: float = 60.0) -> GameState:
    controller = ScriptedController(blinks)
    state = GameState(time_limit_s=limit)
    while state.status is Status.RUNNING:
        state.apply(controller.command(state.time_s))
        state.step()
    return state


def test_hero_waits_then_moves_and_stops_at_wall() -> None:
    s = _empty(dots={5}, pellets=set())
    s.step()
    assert s.hero_x == model.CELLS / 2
    s.apply(Command.RIGHT)
    for _ in range(100):
        s.step()
    assert s.hero_x == model.CELLS - 1
    assert s.time_s == pytest.approx(10.1)


def test_commands_and_log() -> None:
    s = _empty(direction=1)
    s.apply(Command.NONE)
    s.apply(Command.RIGHT)  # already right: no event
    s.apply(Command.REVERSE)
    s.apply(Command.LEFT)  # already left
    assert s.direction == -1
    assert [e.event for e in s.log] == ["turn:left"]


@pytest.mark.parametrize(
    ("hero", "ghost", "expected"),
    [(3.0, None, 1), (15.0, None, -1), (10.0, 4.0, 1), (10.0, 16.0, -1)],
)
def test_reverse_from_standstill_flees(hero: float, ghost: float | None, expected: int) -> None:
    ghosts = [] if ghost is None else [Ghost("Blinky", ghost, 1, ghost)]
    s = GameState(hero_x=hero, ghosts=ghosts)
    s.apply(Command.REVERSE)
    assert s.direction == expected


def test_round_refill_and_win_by_survival() -> None:
    s = _empty(hero_x=17.0, direction=1, dots={18}, pellets=set(), time_limit_s=1.0)
    for _ in range(3):
        s.step()
    assert s.round == 2
    assert s.dots == set(range(1, model.CELLS - 1))
    assert s.pellets == {0, model.CELLS - 1}
    assert s.score == model.DOT_POINTS + model.ROUND_POINTS
    assert s.ghost_speed == pytest.approx(model.GHOST_SPEED * (1 + model.ROUND_SPEEDUP))
    while s.status is Status.RUNNING:
        s.step()
    assert s.status is Status.WON
    assert s.time_s == pytest.approx(1.0)
    s.step()  # no-op after the end
    s.apply(Command.LEFT)
    assert s.log[-1].event == "won"


def test_ghost_waits_in_house() -> None:
    s = GameState(ghosts=[Ghost("Blinky", 10.0, 1, 10.0, release_s=1.0)])
    s.step()
    assert s.lives == model.LIVES  # overlapping but still in the house
    assert s.ghosts[0].x == 10.0


def test_pellet_frightens_and_ghost_is_eaten() -> None:
    s = GameState(
        hero_x=18.6, direction=1, dots={1}, pellets={19}, ghosts=[Ghost("Blinky", 16.0, 1, 2.0)]
    )
    for _ in range(12):
        s.step()
        if s.hero_x == model.CELLS - 1:
            s.apply(Command.LEFT)
    events = [e.event for e in s.log]
    assert "pellet" in events
    assert "ate:Blinky" in events
    g = s.ghosts[0]
    assert g.eaten_count == 1
    assert g.release_s > s.time_s - 1.2  # sent back to the house
    assert s.score == model.PELLET_POINTS + model.GHOST_POINTS


def test_caught_costs_life_grace_then_loses() -> None:
    s = GameState(
        hero_x=5.0,
        direction=-1,
        dots={15},
        pellets=set(),
        ghosts=[Ghost("Blinky", 4.4, 1, 4.4)],
        lives=2,
    )
    s.step()
    assert s.lives == 1
    assert (s.hero_x, s.direction) == (model.CELLS / 2, -1)  # keeps direction
    assert s.ghosts[0].x == 4.4
    assert not s.ghosts[0].active(s.time_s)
    s.ghosts[0].release_s = 0.0
    s.ghosts[0].x = s.hero_x
    s.step()
    assert s.lives == 1  # grace period
    s.grace_left_s = 0.0
    s.ghosts[0].x = s.hero_x
    s.step()
    assert s.status is Status.LOST
    assert [e.event for e in s.log][-2:] == ["caught:Blinky", "lost"]


def test_far_ghost_and_bounce() -> None:
    s = GameState(ghosts=[Ghost("Blinky", 0.05, -1, 2.0)])
    s.step()
    assert s.lives == model.LIVES
    assert s.ghosts[0].direction == 1
    assert s.ghosts[0].x == 0.0


def test_balance_blink_cadence_wins_idle_loses() -> None:
    blink_test = [10.555, 15.505, 20.34, 25.11, 29.465, 35.445, 40.71, 45.645, 50.35, 54.465]
    assert _play(blink_test, limit=57.7).status is Status.WON
    assert _play([]).status is Status.LOST
    rnd = random.Random(1)
    wins = sum(
        _play(sorted(rnd.uniform(0, 60) for _ in range(12))).status is Status.WON for _ in range(30)
    )
    assert 0 < wins < 15  # random input rarely survives


def test_simulate_is_deterministic_and_stops() -> None:
    cmds = {30: Command.REVERSE, 60: Command.REVERSE, 95: Command.REVERSE}
    a = model.simulate(cmds, 700)
    b = model.simulate(cmds, 700)
    assert a.log == b.log
    assert a.status is not Status.RUNNING
    short = model.simulate({}, 5)
    assert short.status is Status.RUNNING
    assert short.time_s == pytest.approx(0.5)
