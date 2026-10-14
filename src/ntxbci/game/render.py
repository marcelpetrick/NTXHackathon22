# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Draw a :class:`GameState` with pygame (window 606 x 86, like the hackathon version)."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import pygame

from ntxbci.game.model import CELLS, GameState, Status

CELL_PX = 30
WALL_PX = 3
TOP_PX = 26
WIDTH = CELLS * CELL_PX + 2 * WALL_PX
HEIGHT = 86
SPRITE_PX = 28

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
SKYBLUE = (0, 191, 255)
RED = (255, 0, 0)
FRIGHT_BLUE = (40, 40, 255)


def asset_path(name: str) -> Path:
    with as_file(files("ntxbci.game") / "assets" / name) as path:
        return Path(path)


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        pygame.font.init()
        self.font = pygame.font.Font(None, 22)
        self.big_font = pygame.font.Font(None, 30)
        self.hero = self._sprite("pacman.png")
        self.ghosts = {n: self._sprite(f"{n}.png") for n in ("Blinky", "Clyde")}

    @staticmethod
    def _sprite(name: str) -> pygame.Surface:
        image = pygame.image.load(str(asset_path(name)))
        return pygame.transform.smoothscale(image.convert_alpha(), (SPRITE_PX, SPRITE_PX))

    @staticmethod
    def cell_centre(x: float) -> tuple[int, int]:
        return int(WALL_PX + x * CELL_PX + CELL_PX / 2), TOP_PX + (HEIGHT - TOP_PX) // 2

    def draw(self, state: GameState, caption: str = "") -> None:
        s = self.surface
        s.fill(BLACK)
        pygame.draw.rect(s, SKYBLUE, (0, TOP_PX - WALL_PX, WIDTH, WALL_PX))
        pygame.draw.rect(s, SKYBLUE, (0, HEIGHT - WALL_PX, WIDTH, WALL_PX))
        pygame.draw.rect(s, SKYBLUE, (0, TOP_PX - WALL_PX, WALL_PX, HEIGHT))
        pygame.draw.rect(s, SKYBLUE, (WIDTH - WALL_PX, TOP_PX - WALL_PX, WALL_PX, HEIGHT))
        for cell in state.dots:
            pygame.draw.circle(s, YELLOW, self.cell_centre(cell), 3)
        for cell in state.pellets:
            pygame.draw.circle(s, WHITE, self.cell_centre(cell), 7)
        for g in state.ghosts:
            sprite = self.ghosts.get(g.name, self.ghosts["Blinky"])
            if state.frightened:
                sprite = sprite.copy()
                sprite.fill(FRIGHT_BLUE, special_flags=pygame.BLEND_RGB_MIN)
            s.blit(sprite, sprite.get_rect(center=self.cell_centre(g.x)))
        hero = self.hero if state.direction >= 0 else pygame.transform.flip(self.hero, True, False)
        s.blit(hero, hero.get_rect(center=self.cell_centre(state.hero_x)))
        hud = f"Score {state.score}   Lives {state.lives}   {state.time_s:5.1f}s"
        if caption:
            hud += f"   {caption}"
        s.blit(self.font.render(hud, True, RED), (8, 4))
        if state.status is not Status.RUNNING:
            msg = "You won!" if state.status is Status.WON else "Game over"
            text = self.big_font.render(msg, True, WHITE)
            s.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 10)))
