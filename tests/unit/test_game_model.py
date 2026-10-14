# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import pytest

from ntxbci.game import model
from ntxbci.game.model import Command, GameState, Ghost, Status


def _empty(**kwargs: object) -> GameState:
    state = GameState(ghosts=[], **kwargs)  # type: ignore[arg-type]
    return state


def test_hero_moves_and_stops_at_wall() -> None:
    s = _empty(dots={5}, pellets=set())
    for _ in range(100):
        s.step()
    assert s.hero_x == model.CELLS - 1
    assert s.time_s == pytest.approx(10.0)


def test_commands_and_log() -> None:
    s = _empty()
    s.apply(Command.NONE)
    s.apply(Command.RIGHT)  # already right: no event
    s.apply(Command.REVERSE)
    s.apply(Command.LEFT)  # already left
    assert s.direction == -1
    assert [e.event for e in s.log] == ["turn:left"]
    s.direction = 0
    s.hero_x = 3
    s.apply(Command.REVERSE)
    assert s.direction == 1
    s.direction, s.hero_x = 0, 15
    s.apply(Command.REVERSE)
    assert s.direction == -1


def test_eating_dots_and_pellet_wins() -> None:
    s = _empty(hero_x=17.0, dots={18}, pellets={19})
    s.step()
    s.step()
    s.step()
    s.step()
    s.step()
    assert s.status is Status.WON
    assert s.score == model.DOT_POINTS
    s.step()  # no-op after the end
    s.apply(Command.LEFT)
    assert s.log[-1].event == "won"


def test_pellet_frightens_and_ghost_is_eaten() -> None:
    s = GameState(hero_x=18.6, dots={1}, pellets={19}, ghosts=[Ghost("Blinky", 16.0, 1, 2.0)])
    for _ in range(12):
        s.step()
        if s.hero_x == model.CELLS - 1:
            s.apply(Command.LEFT)
    events = [e.event for e in s.log]
    assert "pellet" in events
    assert "ate:Blinky" in events
    assert s.ghosts[0].eaten_count == 1
    assert s.score == model.PELLET_POINTS + model.GHOST_POINTS


def test_caught_costs_life_and_resets_then_loses() -> None:
    s = GameState(
        hero_x=5.0,
        direction=-1,
        dots={15},
        pellets=set(),
        ghosts=[Ghost("Clyde", 4.4, 1, 4.4)],
        lives=2,
    )
    s.step()
    assert s.lives == 1
    assert (s.hero_x, s.direction) == (model.CELLS / 2, 0)
    assert s.ghosts[0].x == 4.4
    s.hero_x = 4.2
    s.step()
    assert s.status is Status.LOST
    assert [e.event for e in s.log][-2:] == ["caught:Clyde", "lost"]


def test_ghosts_far_away_do_nothing() -> None:
    s = GameState(hero_x=10, direction=0, ghosts=[Ghost("Blinky", 2.0, 1, 2.0)])
    s.step()
    assert s.lives == model.LIVES


def test_ghosts_bounce() -> None:
    s = GameState(hero_x=10, direction=0, ghosts=[Ghost("Blinky", 0.05, -1, 2.0)])
    s.step()
    assert s.ghosts[0].direction == 1
    assert s.ghosts[0].x == 0.0


def test_simulate_is_deterministic_and_stops() -> None:
    cmds = {30: Command.REVERSE, 60: Command.REVERSE, 95: Command.REVERSE}
    a = model.simulate(cmds, 600)
    b = model.simulate(cmds, 600)
    assert a.log == b.log
    assert a.score == b.score
    assert a.status is not Status.RUNNING or a.time_s == pytest.approx(60.0)
    won = model.simulate({}, 100, state=_empty(hero_x=18.0, dots={19}, pellets=set()))
    assert won.status is Status.WON
    assert won.time_s < 1
