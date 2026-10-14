# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""The pygame main loop, usable interactively, for replays and headless."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pygame

from ntxbci.game.controllers import Controller, KeyboardController
from ntxbci.game.model import TICK_S, TIME_LIMIT_S, Command, GameState, Status
from ntxbci.game.render import HEIGHT, WIDTH, Renderer, asset_path

KEYS = {
    pygame.K_LEFT: Command.LEFT,
    pygame.K_RIGHT: Command.RIGHT,
    pygame.K_SPACE: Command.REVERSE,
}


@dataclass(frozen=True)
class RunOptions:
    realtime: bool = True
    speed: float = 1.0
    max_seconds: float = 120.0
    screenshot: Path | None = None
    """Save the last frame as PNG."""
    caption: str = ""
    headless: bool = False
    """Use SDL's dummy video driver (CI, docker, tests)."""
    time_limit_s: float = TIME_LIMIT_S
    """Survive this long to win."""


DEFAULT_OPTIONS = RunOptions()


def run(controller: Controller, options: RunOptions = DEFAULT_OPTIONS) -> GameState:
    """Play until won/lost, ``max_seconds`` of game time, ESC or window close."""
    if options.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.display.init()
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("NTX Pacman")
        pygame.display.set_icon(pygame.image.load(str(asset_path("icon.png"))))
        renderer = Renderer(screen)
        state = GameState()
        state.time_limit_s = options.time_limit_s
        clock = pygame.time.Clock()
        keyboard = controller if isinstance(controller, KeyboardController) else None
        ticks = round(options.max_seconds / TICK_S)
        quit_requested = False
        for _ in range(ticks):
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    quit_requested = True
                elif event.type == pygame.KEYDOWN and keyboard and event.key in KEYS:
                    keyboard.press(KEYS[event.key])
            if quit_requested:
                break
            state.apply(controller.command(state.time_s))
            state.step()
            renderer.draw(state, options.caption)
            pygame.display.flip()
            if state.status is not Status.RUNNING:
                break
            if options.realtime:
                clock.tick(options.speed / TICK_S)
        renderer.draw(state, options.caption)
        if options.screenshot is not None:
            options.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(options.screenshot))
        return state
    finally:
        pygame.display.quit()
