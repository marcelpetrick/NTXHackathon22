# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
from ntxbci.game.controllers import KeyboardController, ScriptedController, tick_of
from ntxbci.game.model import Command, GameState


def test_scripted_controller_fires_once_per_time() -> None:
    c = ScriptedController([1.05, 0.25, 1.0, 1.02])
    assert c.remaining == 4
    seen = [c.command(t / 10) for t in range(15)]
    # 0.25 fires on the tick starting at 0.3, 1.0 on 1.0, and 1.02 + 1.05 collapse into 1.1
    assert [i for i, cmd in enumerate(seen) if cmd is Command.REVERSE] == [3, 10, 11]
    assert c.remaining == 0


def test_keyboard_controller_consumes_press() -> None:
    k = KeyboardController()
    assert k.command(0) is Command.NONE
    k.press(Command.LEFT)
    assert k.command(0.1) is Command.LEFT
    assert k.command(0.2) is Command.NONE


def test_tick_of() -> None:
    assert tick_of(0.0) == 0
    assert tick_of(0.25) == 3
    assert tick_of(1.0) == 10
    assert tick_of(1.1) == 11  # 1.1 / 0.1 == 11.000000000000002 in floats


def test_controller_and_tick_of_agree_for_every_sample_time() -> None:
    """Regression: blinks on tick boundaries used to fire one tick before tick_of said."""
    state = GameState(ghosts=[], time_limit_s=1e9)
    clock = []
    for _ in range(601):
        clock.append(state.time_s)
        state.step()
    for k in range(0, 200 * 60):  # every Ganglion sample time in 60 s
        blink = k / 200
        controller = ScriptedController([blink])
        fired = next(i for i, t in enumerate(clock) if controller.command(t) is Command.REVERSE)
        assert fired == tick_of(blink), blink
