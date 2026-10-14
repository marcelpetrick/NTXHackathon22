# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The pygame loop with SDL's dummy driver."""

from pathlib import Path

import pygame
import pytest

from ntxbci.game import app
from ntxbci.game.controllers import KeyboardController, ScriptedController
from ntxbci.game.model import Command, GameState, Ghost, Status
from ntxbci.game.render import HEIGHT, WIDTH


def _opts(**kw: object) -> app.RunOptions:
    base: dict[str, object] = {"realtime": False, "headless": True, "max_seconds": 3.0}
    base.update(kw)
    return app.RunOptions(**base)  # type: ignore[arg-type]


def test_scripted_run_and_screenshot(tmp_path: Path) -> None:
    shot = tmp_path / "shots" / "game.png"
    state = app.run(ScriptedController([1.0]), _opts(screenshot=shot, caption="replay"))
    assert state.time_s == pytest.approx(3.0)
    assert [e.event for e in state.log] == ["turn:left"]
    image = pygame.image.load(str(shot))
    assert image.get_size() == (WIDTH, HEIGHT)


def test_realtime_with_speedup_finishes_quickly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    opts = _opts(realtime=True, speed=50.0, max_seconds=1.0, headless=False)
    state = app.run(ScriptedController([]), opts)
    assert state.time_s == pytest.approx(1.0)


def test_keyboard_and_escape(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT)],
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)],
        [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)],
    ]
    monkeypatch.setattr(pygame.event, "get", lambda: events.pop(0) if events else [])
    state = app.run(KeyboardController(), _opts())
    assert [e.event for e in state.log] == ["turn:left"]
    assert state.time_s == pytest.approx(0.2)


def test_window_close_and_game_over_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "GameState", _losing_state)
    state = app.run(ScriptedController([]), _opts())
    assert state.status is Status.LOST
    monkeypatch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.QUIT)])
    assert app.run(KeyboardController(), _opts()).time_s == 0


def _losing_state() -> GameState:
    return GameState(hero_x=5.0, direction=-1, lives=1, ghosts=[Ghost("Clyde", 4.6, 1, 4.6)])


def test_frightened_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "GameState", lambda: GameState(fright_left_s=5.0))
    state = app.run(ScriptedController([]), _opts(max_seconds=0.2))
    assert state.frightened
    assert Command.NONE.value == "none"
