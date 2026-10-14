# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Replay check: recording -> blink detector -> game, verified end to end.

The recording's clock *is* the game clock (t = 0 at the first sample). Every detected blink
is fed to a :class:`~ntxbci.game.controllers.ScriptedController`, which reverses Pacman on
the next tick. The check passes when

1. detection meets ``min_f1`` against the manifest's ground truth (if it has events),
2. every blink that happened while the game was running produced exactly one turn,
   on the expected tick, and nothing else turned Pacman,
3. two runs give identical game logs (determinism).

This is the automated regression baseline for continuing the hackathon work: change the
detector or the game, rerun ``ntxbci replay``, and see immediately whether the chain holds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ntxbci.events import DEFAULT_PARAMS, BlinkParams, detect_blinks, match_events
from ntxbci.game.controllers import ScriptedController, tick_of
from ntxbci.game.model import TICK_S, GameState, LogEntry, Status
from ntxbci.io import load_recording
from ntxbci.manifest import Manifest

_EPS = 1e-6


@dataclass(frozen=True)
class DetectionReport:
    expected: int
    detected: int
    precision: float
    recall: float
    f1: float
    mean_latency_s: float
    missed_s: tuple[float, ...]
    spurious_s: tuple[float, ...]


@dataclass(frozen=True)
class GameReport:
    status: str
    """``won`` = survived the whole recording."""
    score: int
    lives: int
    duration_s: float
    turns: int
    blinks_applied: int
    blinks_after_end: int


@dataclass(frozen=True)
class ReplayReport:
    recording: str
    blinks_s: tuple[float, ...]
    detection: DetectionReport | None
    game: GameReport
    deterministic: bool
    problems: tuple[str, ...] = field(default_factory=tuple)
    min_f1: float = 1.0

    @property
    def passed(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["passed"] = self.passed
        return out


def play_blinks(blinks_s: list[float], duration_s: float) -> GameState:
    """Run the game rules for ``duration_s`` with a reverse at every blink time."""
    controller = ScriptedController(blinks_s)
    state = GameState(time_limit_s=duration_s)
    for _ in range(round(duration_s / TICK_S)):
        state.apply(controller.command(state.time_s))
        state.step()
        if state.status is not Status.RUNNING:
            break
    return state


def _check_reactions(blinks_s: list[float], state: GameState) -> tuple[list[str], int, int]:
    """Compare turn events with the ticks the blinks should have landed on."""
    expected_ticks = sorted({tick_of(b) for b in blinks_s})
    end_tick = round(state.time_s / TICK_S)
    applied = [t for t in expected_ticks if t < end_tick]
    turns: list[LogEntry] = [e for e in state.log if e.event.startswith("turn:")]
    turn_ticks = [round(e.time_s / TICK_S) for e in turns]
    problems = []
    if turn_ticks != applied:
        missing = sorted(set(applied) - set(turn_ticks))
        extra = sorted(set(turn_ticks) - set(applied))
        problems.append(
            f"game reaction mismatch: missing turns at ticks {missing}, unexpected {extra}"
        )
    return problems, len(applied), len(expected_ticks) - len(applied)


def replay(
    manifest: Manifest,
    recording_id: str,
    params: BlinkParams = DEFAULT_PARAMS,
    min_f1: float = 1.0,
) -> ReplayReport:
    entry = manifest.get(recording_id)
    if entry.kind == "impedance":
        raise ValueError(f"{recording_id} is an impedance check, not a recording")
    rec = load_recording(manifest.file(entry))
    blinks = [b.time_s for b in detect_blinks(rec, params)]
    problems: list[str] = []

    detection = None
    if entry.events is not None:
        m = match_events(blinks, entry.events.times_s, entry.events.tolerance_s)
        detection = DetectionReport(
            expected=len(entry.events.times_s),
            detected=len(blinks),
            precision=m.precision,
            recall=m.recall,
            f1=m.f1,
            mean_latency_s=m.mean_latency_s,
            missed_s=m.false_negatives,
            spurious_s=m.false_positives,
        )
        if m.f1 + _EPS < min_f1:
            problems.append(f"detection F1 {m.f1:.3f} below required {min_f1:.3f}")

    state = play_blinks(blinks, rec.duration)
    again = play_blinks(blinks, rec.duration)
    deterministic = state.log == again.log and state.score == again.score
    if not deterministic:  # pragma: no cover - would indicate hidden randomness
        problems.append("game is not deterministic")
    reaction_problems, applied, after_end = _check_reactions(blinks, state)
    problems.extend(reaction_problems)

    game = GameReport(
        status=state.status.value,
        score=state.score,
        lives=state.lives,
        duration_s=round(state.time_s, 6),
        turns=sum(1 for e in state.log if e.event.startswith("turn:")),
        blinks_applied=applied,
        blinks_after_end=after_end,
    )
    return ReplayReport(
        recording=recording_id,
        blinks_s=tuple(round(b, 3) for b in blinks),
        detection=detection,
        game=game,
        deterministic=deterministic,
        problems=tuple(problems),
        min_f1=min_f1,
    )
