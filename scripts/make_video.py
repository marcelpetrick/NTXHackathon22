# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# make_video.py - render showcase clips (<= 30 s) of the blink-test replay: the recorded EEG
# next to the game it steers, every detected blink travelling from its spike to Pacman.
# Two cuts: "explainer" (16:9, real time, captions for non-BCI viewers) and "fastcut"
# (1:1, the whole recording at 2.6x speed). Needs ffmpeg with libx264.
# Usage: uv run python scripts/make_video.py [--cut explainer|fastcut|all] [--out DIR] [--gif]
"""Render the LinkedIn/README showcase videos from the real blink-test recording."""

from __future__ import annotations

import argparse
import copy
import math
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame

from ntxbci.events import DEFAULT_PARAMS, blink_score, detect_blinks
from ntxbci.game.controllers import ScriptedController
from ntxbci.game.model import TICK_S, GameState, Status
from ntxbci.game.render import HEIGHT as GAME_H
from ntxbci.game.render import WIDTH as GAME_W
from ntxbci.game.render import Renderer, asset_path
from ntxbci.io import Recording, load_recording
from ntxbci.manifest import load_manifest
from ntxbci.processing import bandpass, notch

FPS = 30
REPO_URL = "github.com/marcelpetrick/NTXHackathon22"
TEAM = "Team: Shuhong Huang · Thomas Mullen · Marcel Petrick"
RECORDING = "blink-test"

BG_TOP = (8, 12, 28)
BG_BOTTOM = (18, 26, 56)
PANEL = (16, 23, 46)
PANEL_EDGE = (44, 62, 110)
TEXT = (232, 238, 255)
MUTED = (140, 155, 195)
CYAN = (0, 220, 255)
PINK = (255, 60, 160)
PAC = (255, 214, 0)
CHANNEL_COLOURS = ((0, 220, 255), (120, 255, 140), (255, 170, 60), (190, 130, 255))

Colour = tuple[int, int, int]


# --------------------------------------------------------------------------- data


@dataclass
class Data:
    """Everything the clips show, computed once from the real recording."""

    fs: float
    duration: float
    eeg: np.ndarray
    """Display-filtered EEG, ``(n, 4)`` in microvolts."""
    score: np.ndarray
    """Blink-detector score (robust z), one value per sample."""
    threshold: float
    blinks: list[float]
    snaps: list[GameState] = field(default_factory=list)

    @classmethod
    def load(cls) -> Data:
        manifest = load_manifest()
        rec: Recording = load_recording(manifest.file(manifest.get(RECORDING)))
        eeg = bandpass(notch(rec.exg, rec.fs), rec.fs, 0.5, 20.0)
        settle = int(DEFAULT_PARAMS.settle_s * rec.fs)
        eeg[:settle] *= np.linspace(0.0, 1.0, settle)[:, None] ** 4  # hide the amp transient
        data = cls(
            fs=rec.fs,
            duration=rec.duration,
            eeg=eeg,
            score=blink_score(rec.exg, rec.fs),
            threshold=DEFAULT_PARAMS.threshold_z,
            blinks=[b.time_s for b in detect_blinks(rec)],
        )
        data.snaps = simulate(data.blinks, rec.duration)
        return data

    def blinks_until(self, t: float) -> list[float]:
        return [b for b in self.blinks if b <= t]


def simulate(blinks: list[float], duration: float) -> list[GameState]:
    """Game state after every tick, exactly like ``ntxbci.replay.play_blinks``."""
    controller = ScriptedController(blinks)
    state = GameState(time_limit_s=duration)
    snaps = [copy.deepcopy(state)]
    for _ in range(round(duration / TICK_S)):
        state.apply(controller.command(state.time_s))
        state.step()
        snaps.append(copy.deepcopy(state))
        if state.status is not Status.RUNNING:
            break
    return snaps


def game_state_at(snaps: list[GameState], t: float) -> GameState:
    """Interpolated state at game time ``t`` (positions only, for smooth motion)."""
    k = min(int(t / TICK_S), len(snaps) - 1)
    a, b = snaps[k], snaps[min(k + 1, len(snaps) - 1)]
    frac = min(1.0, max(0.0, t / TICK_S - k))
    out = copy.copy(b if frac > 0 else a)
    if abs(b.hero_x - a.hero_x) < 1.0:
        out.hero_x = a.hero_x + (b.hero_x - a.hero_x) * frac
    ghosts = []
    for ga, gb in zip(a.ghosts, b.ghosts, strict=True):
        x = ga.x + (gb.x - ga.x) * frac if abs(gb.x - ga.x) < 1.0 else gb.x
        ghosts.append(replace(gb, x=x))
    out.ghosts = ghosts
    return out


# --------------------------------------------------------------------------- drawing helpers


class Fonts:
    def __init__(self, scale: float) -> None:
        def make(size: int, bold: bool = True, mono: bool = False) -> pygame.font.Font:
            names = ("notosansmono", "dejavusansmono") if mono else ("notosans", "dejavusans")
            for name in names:
                path = pygame.font.match_font(name, bold=bold)
                if path:
                    return pygame.font.Font(path, round(size * scale))
            return pygame.font.Font(None, round(size * scale * 1.3))

        self.hero = make(84)
        self.title = make(52)
        self.big = make(40)
        self.mid = make(28)
        self.body = make(26, bold=False)
        self.small = make(20, bold=False)
        self.mono = make(22, mono=True)
        self.mono_big = make(44, mono=True)


def gradient(size: tuple[int, int]) -> pygame.Surface:
    w, h = size
    col = np.linspace(0, 1, h)[:, None]
    rgb = np.array(BG_TOP) * (1 - col) + np.array(BG_BOTTOM) * col
    arr = np.repeat(rgb[None, :, :], w, axis=0).astype(np.uint8)
    return pygame.surfarray.make_surface(arr)


def text(  # noqa: PLR0917 - positional like pygame's own draw helpers
    surf: pygame.Surface,
    font: pygame.font.Font,
    msg: str,
    pos: tuple[float, float],
    colour: Colour = TEXT,
    anchor: str = "topleft",
    alpha: float = 1.0,
) -> pygame.Rect:
    img = font.render(msg, True, colour)
    if alpha < 1.0:
        img.set_alpha(round(255 * max(0.0, alpha)))
    rect = img.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surf.blit(img, rect)
    return rect


def panel(surf: pygame.Surface, rect: pygame.Rect, glow: float = 0.0) -> None:
    pygame.draw.rect(surf, PANEL, rect, border_radius=18)
    edge = tuple(round(e + (c - e) * glow) for e, c in zip(PANEL_EDGE, PINK, strict=True))
    pygame.draw.rect(surf, edge, rect, width=2, border_radius=18)


def glow_circle(surf: pygame.Surface, centre: tuple[float, float], r: float, c: Colour) -> None:
    layer = pygame.Surface((int(r * 6), int(r * 6)), pygame.SRCALPHA)
    mid = layer.get_width() / 2
    for i, alpha in ((3.0, 30), (2.0, 60), (1.3, 120), (1.0, 255)):
        pygame.draw.circle(layer, (*c, alpha), (mid, mid), r * i)
    surf.blit(layer, (centre[0] - mid, centre[1] - mid), special_flags=pygame.BLEND_RGBA_ADD)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def wrap(font: pygame.font.Font, msg: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in msg.split():
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return [*lines, line] if line else lines


# --------------------------------------------------------------------------- layouts


@dataclass(frozen=True)
class Layout:
    size: tuple[int, int]
    eeg: pygame.Rect
    pipeline: pygame.Rect
    game: pygame.Rect
    stats: pygame.Rect
    caption: pygame.Rect
    window_s: float
    scale: float


WIDE = Layout(
    size=(1920, 1080),
    eeg=pygame.Rect(60, 130, 1000, 760),
    pipeline=pygame.Rect(1110, 130, 750, 200),
    game=pygame.Rect(1110, 360, 750, 196),
    stats=pygame.Rect(1110, 586, 750, 304),
    caption=pygame.Rect(60, 920, 1800, 120),
    window_s=6.0,
    scale=1.0,
)
SQUARE = Layout(
    size=(1080, 1080),
    eeg=pygame.Rect(40, 120, 1000, 420),
    pipeline=pygame.Rect(40, 556, 1000, 92),
    game=pygame.Rect(40, 664, 1000, 142),
    stats=pygame.Rect(40, 820, 1000, 90),
    caption=pygame.Rect(40, 914, 1000, 140),
    window_s=9.0,
    scale=0.9,
)

PIPELINE = ("Electrodes", "Filter", "Detect spike", "Command", "Pacman turns")


# --------------------------------------------------------------------------- scenes


@dataclass(frozen=True)
class Caption:
    start: float
    """Recording time (s) at which the caption appears."""
    msg: str


@dataclass(frozen=True)
class Play:
    duration: float
    rec_start: float
    rec_end: float
    captions: Sequence[Caption] = ()
    badge: str = ""
    hold: float = 0.0
    """Seconds the last frame stays on screen (the payoff)."""

    @property
    def speed(self) -> float:
        return (self.rec_end - self.rec_start) / (self.duration - self.hold)


@dataclass(frozen=True)
class Card:
    duration: float
    kind: str
    """``intro`` or ``outro``."""
    title: str
    subtitle: str = ""
    lines: Sequence[str] = ()


Scene = Play | Card


class Painter:
    """Draws one frame of a scene onto a surface of the layout's size."""

    def __init__(self, data: Data, layout: Layout) -> None:
        self.data = data
        self.lay = layout
        self.f = Fonts(layout.scale)
        self.bg = gradient(layout.size)
        self.game_surface = pygame.Surface((GAME_W, GAME_H))
        self.renderer = Renderer(self.game_surface)
        pac = pygame.image.load(str(asset_path("pacman.png"))).convert_alpha()
        self.pac = pygame.transform.smoothscale(pac, (round(90 * layout.scale),) * 2)
        lanes = data.eeg[int(DEFAULT_PARAMS.settle_s * data.fs) :]
        self.uv_scale = float(np.percentile(np.abs(lanes), 99.7))

    # ----- shared pieces

    def header(self, surf: pygame.Surface, badge: str) -> None:
        w = self.lay.size[0]
        text(surf, self.f.mid, "NeuroTechX Hackathon 2022", (self.lay.eeg.left, 34), PAC)
        sub = "Pacman steered by blinks, replayed from a real EEG recording"
        text(surf, self.f.small, sub, (self.lay.eeg.left, 34 + self.f.mid.get_height()), MUTED)
        if badge:
            r = text(surf, self.f.mono, badge, (w - 60, 44), PINK, "topright")
            pygame.draw.rect(surf, PINK, r.inflate(24, 12), 2, border_radius=10)

    def x_of(self, t: float, now: float) -> float:
        left, width = self.lay.eeg.left + 70, (self.lay.eeg.width - 100) * 0.88
        return left + width - (now - t) / self.lay.window_s * width

    def eeg_panel(self, surf: pygame.Surface, now: float, speed: float) -> None:
        d, rect = self.data, self.lay.eeg
        recent = [b for b in d.blinks_until(now) if (now - b) / speed < 0.6]
        panel(surf, rect, glow=max((1 - (now - b) / speed / 0.6 for b in recent), default=0))
        pad = 30
        text(surf, self.f.mid, "Brain signals (EEG)", (rect.left + pad, rect.top + 18), TEXT)
        note = "4 electrodes · 200 samples/s"
        text(surf, self.f.small, note, (rect.right - pad, rect.top + 26), MUTED, "topright")
        top = rect.top + 60 + self.f.mid.get_height()
        score_h = rect.height * 0.27
        lanes_h = rect.bottom - top - score_h - 30
        lane_h = lanes_h / 4
        t0 = max(0.0, now - self.lay.window_s)
        i0, i1 = int(t0 * d.fs), max(int(t0 * d.fs) + 2, int(now * d.fs))
        ts = np.arange(i0, i1) / d.fs
        xs = [self.x_of(t, now) for t in ts]
        for ch in range(4):
            mid = top + lane_h * (ch + 0.5)
            ys = mid - np.clip(d.eeg[i0:i1, ch] / self.uv_scale, -1.2, 1.2) * lane_h * 0.5
            self.trace(surf, xs, ys, CHANNEL_COLOURS[ch])
            text(surf, self.f.small, f"ch{ch + 1}", (rect.left + 12, mid), MUTED, "midleft")
        lane = pygame.Rect(rect.left, rect.bottom - 20 - score_h, rect.width, score_h)
        self.score_lane(surf, lane, xs, slice(i0, i1))
        self.blink_marks(surf, now, top, rect.bottom - 20)
        x_now = self.x_of(now, now)
        pygame.draw.line(surf, (255, 255, 255), (x_now, top - 6), (x_now, rect.bottom - 20), 2)
        text(surf, self.f.small, "now", (x_now + 8, top - 10), TEXT)

    def score_lane(
        self, surf: pygame.Surface, rect: pygame.Rect, xs: list[float], span: slice
    ) -> None:
        """Detector score (clipped at z = 40) with the dashed detection threshold."""
        d = self.data
        top_z = 40.0
        h = rect.height
        base = rect.bottom
        thr_y = base - d.threshold / top_z * h
        for x in range(rect.left + 70, rect.right - 30, 18):
            pygame.draw.line(surf, PINK, (x, thr_y), (x + 9, thr_y), 2)
        text(surf, self.f.small, "blink", (rect.left + 12, base - h * 0.5), MUTED, "midleft")
        x_label = self.x_of(0, 0) + 10  # right of the "now" line, where no data is drawn
        text(surf, self.f.small, "threshold", (x_label, thr_y - 4), PINK, "bottomleft")
        ys = base - np.clip(d.score[span], 0, top_z) / top_z * h
        self.trace(surf, xs, ys, (255, 255, 255))

    @staticmethod
    def trace(surf: pygame.Surface, xs: Sequence[float], ys: np.ndarray, c: Colour) -> None:
        if len(xs) < 2:
            return
        pts = list(zip(xs, ys.tolist(), strict=True))
        dim = tuple(v // 3 for v in c)
        pygame.draw.lines(surf, dim, False, pts, 5)
        pygame.draw.aalines(surf, c, False, pts)

    def blink_marks(self, surf: pygame.Surface, now: float, top: float, bottom: float) -> None:
        left = self.lay.eeg.left + 70
        for n, b in enumerate(self.data.blinks, start=1):
            if b > now or now - b > self.lay.window_s:
                continue
            x = self.x_of(b, now)
            if x < left:
                continue
            band = pygame.Surface((26, int(bottom - top)), pygame.SRCALPHA)
            band.fill((*PINK, 45))
            surf.blit(band, (x - 13, top))
            text(surf, self.f.mono, f"#{n}", (x, top - 4), PINK, "midbottom")

    def pipeline(self, surf: pygame.Surface, now: float, speed: float) -> None:
        rect = self.lay.pipeline
        if self.lay is WIDE:
            panel(surf, rect)
            text(surf, self.f.mid, "How it works", (rect.left + 24, rect.top + 16))
        last = max(self.data.blinks_until(now), default=-99.0)
        age = (now - last) / speed
        n = len(PIPELINE)
        gap = 12
        y = rect.top + (70 if self.lay is WIDE else 14)
        chip_w = (rect.width - 48 - gap * (n - 1)) / n
        chip_h = rect.bottom - y - (24 if self.lay is WIDE else 10)
        for i, name in enumerate(PIPELINE):
            lit = 1.0 - ease((age - i * 0.09) / 0.5) if age >= i * 0.09 else 0.0
            r = pygame.Rect(rect.left + 24 + i * (chip_w + gap), y, chip_w, chip_h)
            fill = tuple(round(p + (c - p) * lit) for p, c in zip(PANEL, PINK, strict=True))
            pygame.draw.rect(surf, fill, r, border_radius=12)
            pygame.draw.rect(surf, PANEL_EDGE, r, 2, border_radius=12)
            lines = wrap(self.f.small, name, int(chip_w) - 12)
            lh = self.f.small.get_height()
            for j, line in enumerate(lines):
                cy = r.centery + (j - (len(lines) - 1) / 2) * lh
                text(surf, self.f.small, line, (r.centerx, cy), TEXT, "center")

    def game_view(self, surf: pygame.Surface, now: float) -> pygame.Rect:
        state = game_state_at(self.data.snaps, now)
        self.renderer.draw(state)
        rect = self.lay.game
        if self.lay is WIDE:
            panel(surf, rect)
            text(surf, self.f.mid, "The game", (rect.left + 24, rect.top + 16))
            w = rect.width - 48
            dest = pygame.Rect(rect.left + 24, rect.top + 66, w, round(w * GAME_H / GAME_W))
        else:
            w = rect.width
            dest = pygame.Rect(rect.left, rect.top, w, round(w * GAME_H / GAME_W))
        surf.blit(pygame.transform.smoothscale(self.game_surface, dest.size), dest)
        sx = dest.width / GAME_W
        hero = self.renderer.cell_centre(state.hero_x)
        return pygame.Rect(dest.left + hero[0] * sx, dest.top + hero[1] * sx, 1, 1)

    def stats(self, surf: pygame.Surface, now: float) -> None:
        state = game_state_at(self.data.snaps, now)
        count = len(self.data.blinks_until(now))
        items = (
            ("BLINKS", f"{count}/{len(self.data.blinks)}"),
            ("SCORE", str(state.score)),
            ("LIVES", str(state.lives)),
            ("TIME", f"{min(now, self.data.duration):4.1f}s"),
        )
        rect = self.lay.stats
        if self.lay is WIDE:
            panel(surf, rect)
            top = rect.top + 30
        else:
            top = rect.top
        cell = rect.width / len(items)
        for i, (label, value) in enumerate(items):
            cx = rect.left + cell * (i + 0.5)
            text(surf, self.f.small, label, (cx, top), MUTED, "midtop")
            colour = PINK if label == "BLINKS" else TEXT
            text(surf, self.f.mono_big, value, (cx, top + self.f.small.get_height()), colour,
                 "midtop")  # fmt: skip
        if self.lay is WIDE:
            self.event_feed(surf, rect, now)

    def event_feed(self, surf: pygame.Surface, rect: pygame.Rect, now: float) -> None:
        y = rect.top + 40 + self.f.small.get_height() + self.f.mono_big.get_height()
        state = game_state_at(self.data.snaps, now)
        turns = [e for e in state.log if e.event.startswith("turn:")]
        rows = []
        for n, b in enumerate(self.data.blinks_until(now), start=1):
            way = turns[n - 1].event.split(":")[1] if n <= len(turns) else "…"
            rows.append(f"#{n:<2} blink at {b:5.2f}s  ->  Pacman turns {way}")
        for j, row in enumerate(rows[-3:]):
            alpha = 1.0 if j == len(rows[-3:]) - 1 else 0.55
            text(surf, self.f.mono, row, (rect.left + 30, y + j * 32), TEXT, alpha=alpha)

    def fly(self, surf: pygame.Surface, now: float, speed: float, hero: pygame.Rect) -> None:
        """A glowing dot carries each blink from its spike to Pacman, then a ring pops."""
        d = self.data
        for n, b in enumerate(d.blinks, start=1):
            age = (now - b) / speed
            if not 0 <= age < 1.4:
                continue
            start = (self.x_of(b, now), self.lay.eeg.bottom - 20 - self.lay.eeg.height * 0.2)
            end = (hero.left, hero.top)
            p = ease(age / 0.55)
            if age < 0.55:
                ctrl = ((start[0] + end[0]) / 2, min(start[1], end[1]) - 160 * self.lay.scale)
                for k in range(12):
                    q = max(0.0, p - k * 0.015)
                    x = (1 - q) ** 2 * start[0] + 2 * (1 - q) * q * ctrl[0] + q * q * end[0]
                    y = (1 - q) ** 2 * start[1] + 2 * (1 - q) * q * ctrl[1] + q * q * end[1]
                    glow_circle(surf, (x, y), 7 - k * 0.45, PINK)
            else:
                fade = (age - 0.55) / 0.85
                ring = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                pygame.draw.circle(ring, (*PINK, round(255 * (1 - fade))), end, 18 + 70 * fade, 4)
                surf.blit(ring, (0, 0))
                rise = 40 + 30 * fade
                text(surf, self.f.big, f"#{n} blink -> turn!", (end[0], end[1] - rise), PINK,
                     "midbottom", alpha=1 - fade)  # fmt: skip

    def caption(self, surf: pygame.Surface, scene: Play, now: float) -> None:
        current = [c for c in scene.captions if c.start <= now]
        if not current:
            return
        cap = current[-1]
        alpha = ease((now - cap.start) / scene.speed / 0.4)
        rect = self.lay.caption
        lines = wrap(self.f.big, cap.msg, rect.width - 40)
        lh = self.f.big.get_height()
        for j, line in enumerate(lines):
            y = rect.centery + (j - (len(lines) - 1) / 2) * lh
            text(surf, self.f.big, line, (rect.centerx, y), TEXT, "center", alpha)

    # ----- scenes

    def play(self, surf: pygame.Surface, scene: Play, u: float) -> None:
        now = min(scene.rec_end, scene.rec_start + u * scene.speed)
        surf.blit(self.bg, (0, 0))
        self.header(surf, scene.badge)
        self.eeg_panel(surf, now, scene.speed)
        self.pipeline(surf, now, scene.speed)
        hero = self.game_view(surf, now)
        self.stats(surf, now)
        self.caption(surf, scene, now)
        if now < self.data.duration - 1e-6:
            self.fly(surf, now, scene.speed, hero)
            return
        msg = f"Survived {self.data.duration:.0f} s  ·  {len(self.data.blinks)}/10 blinks"
        img = self.f.title.render(msg, True, PAC)
        box = img.get_rect(center=self.lay.game.center).inflate(60, 30)
        pygame.draw.rect(surf, PANEL, box, border_radius=16)
        pygame.draw.rect(surf, PAC, box, 3, border_radius=16)
        surf.blit(img, img.get_rect(center=box.center))

    def card(self, surf: pygame.Surface, scene: Card, u: float) -> None:
        surf.blit(self.bg, (0, 0))
        w, h = self.lay.size
        s = self.lay.scale
        lane_y = h * (0.72 if scene.kind == "intro" else 0.8)
        x_pac = -100 + (w + 200) * (u / scene.duration)
        for x in range(60, w - 40, round(60 * s)):
            if x > x_pac:
                pygame.draw.circle(surf, PAC, (x, lane_y), 6 * s)
        bob = math.sin(u * 14) * 4 * s
        surf.blit(self.pac, self.pac.get_rect(center=(x_pac, lane_y + bob)))
        fade = ease(u / 0.6)
        y = h * (0.3 if scene.kind == "intro" else 0.22)
        if scene.kind == "intro":
            text(surf, self.f.mid, "NeuroTechX Hackathon 2022", (w / 2, y - 90 * s), PAC, "center",
                 fade)  # fmt: skip
        title_lines = wrap(self.f.hero, scene.title, w - 160)
        for j, line in enumerate(title_lines):
            text(surf, self.f.hero, line, (w / 2, y + j * self.f.hero.get_height()), TEXT,
                 "center", fade)  # fmt: skip
        y += len(title_lines) * self.f.hero.get_height()
        if scene.subtitle:
            colour = CYAN if scene.kind == "outro" else MUTED
            text(surf, self.f.big, scene.subtitle, (w / 2, y + 10), colour, "center",
                 ease((u - 0.3) / 0.6))  # fmt: skip
            y += self.f.big.get_height() + 30
        for j, line in enumerate(scene.lines):
            for k, part in enumerate(wrap(self.f.body, line, w - 200)):
                y += self.f.body.get_height() * (1.0 if k else 1.3)
                text(surf, self.f.body, part, (w / 2, y), TEXT, "center",
                     ease((u - 0.6 - 0.3 * j) / 0.6))  # fmt: skip


# --------------------------------------------------------------------------- cuts


def explainer(data: Data) -> tuple[Layout, list[Scene]]:
    """16:9, real time, explains every step for viewers who never heard of a BCI."""
    b = data.blinks
    return WIDE, [
        Card(
            4.0,
            "intro",
            "Can you play Pacman with a blink?",
            "A tiny brain-computer interface (BCI)",
            ("A BCI turns signals measured on the head into commands for a computer.",),
        ),
        Play(
            20.5,
            8.0,
            28.5,
            (
                Caption(8.0, "Four electrodes on the forehead record electrical activity."),
                Caption(b[0] - 0.05, "A blink causes a big spike. The detector spots it..."),
                Caption(b[1] - 0.05, "...and turns it into a command: Pacman reverses."),
                Caption(b[2] - 0.05, "One blink = one bit of control. Enough to dodge the ghost."),
                Caption(b[3] - 0.05, "Real hackathon data from 2022, replayed: 10/10 blinks hit."),
            ),
            badge="real-time replay",
        ),
        Card(
            4.5,
            "outro",
            "Open source on GitHub",
            REPO_URL,
            (
                "Recordings, blink detector, game and an automated replay check (GPLv3).",
                TEAM,
            ),
        ),
    ]


def fastcut(data: Data) -> tuple[Layout, list[Scene]]:
    """1:1, the whole 58 s recording at ~2.6x: rhythm and payoff, few words."""
    return SQUARE, [
        Card(2.5, "intro", "Blink. Pacman turns.", "EEG-controlled, no hands"),
        Play(
            23.5,
            0.0,
            data.duration,
            (
                Caption(0.0, "Real EEG from the NeuroTechX Hackathon 2022"),
                Caption(data.blinks[0] - 0.1, "Every spike is a blink -> a command"),
                Caption(data.blinks[3] - 0.1, "Detected 0.26 s after the blink, on average"),
                Caption(data.blinks[6] - 0.1, "Blinks are eye muscles, picked up by the EEG"),
                Caption(data.blinks[8] - 0.1, "10/10 blinks detected. Pacman survives."),
            ),
            badge=f"{data.duration / 22.0:.1f}x speed",
            hold=1.5,
        ),
        Card(3.0, "outro", "Try it yourself", REPO_URL, ("Open source · Python · GPLv3", TEAM)),
    ]


CUTS = {"explainer": explainer, "fastcut": fastcut}


def frames(scenes: list[Scene]) -> list[tuple[Scene, float]]:
    out: list[tuple[Scene, float]] = []
    for scene in scenes:
        out.extend((scene, i / FPS) for i in range(round(scene.duration * FPS)))
    return out


def render(name: str, data: Data, out_dir: Path, gif: bool) -> Path:
    layout, scenes = CUTS[name](data)
    total = sum(s.duration for s in scenes)
    if total > 30:
        raise SystemExit(f"{name}: {total:.1f} s is longer than 30 s")
    painter = Painter(data, layout)
    surf = pygame.Surface(layout.size)
    black = pygame.Surface(layout.size)
    out = out_dir / f"ntxbci-{name}.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{layout.size[0]}x{layout.size[1]}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(out),
    ]  # fmt: skip
    with subprocess.Popen(cmd, stdin=subprocess.PIPE) as proc:
        assert proc.stdin is not None
        for scene, u in frames(scenes):
            if isinstance(scene, Play):
                painter.play(surf, scene, u)
            else:
                painter.card(surf, scene, u)
            edge = min(u, scene.duration - u)
            if edge < 0.3:
                black.set_alpha(round(255 * (1 - edge / 0.3)))
                surf.blit(black, (0, 0))
            proc.stdin.write(pygame.image.tobytes(surf, "RGB"))
        proc.stdin.close()
    if proc.returncode:
        raise SystemExit(f"ffmpeg failed for {name}")
    if gif:
        to_gif(out, out.with_suffix(".gif"))
    return out


def to_gif(mp4: Path, gif: Path) -> None:
    graph = (
        "fps=12,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=4"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", graph, str(gif)], check=True
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cut", choices=[*CUTS, "all"], default="all")
    parser.add_argument("--out", type=Path, default=Path("build/video"))
    parser.add_argument("--gif", action="store_true", help="also write a 640 px GIF per cut")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found")
    pygame.init()
    pygame.display.set_mode((1, 1))
    data = Data.load()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in CUTS if args.cut == "all" else [args.cut]:
        print(render(name, data, args.out, args.gif))


if __name__ == "__main__":
    main()
