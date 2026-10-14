# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Sources of game commands: keyboard events and replayed blink detections."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol

from ntxbci.game.model import TICK_S, Command


class Controller(Protocol):
    def command(self, time_s: float) -> Command:
        """Command for the tick that starts at ``time_s`` (game clock)."""
        ...  # pragma: no cover - protocol


class ScriptedController:
    """Emit ``REVERSE`` once at each given time - used to replay blink detections.

    A blink at ``t`` triggers on tick :func:`tick_of` ``(t)``, the first tick whose start is
    ``>= t``, i.e. with at most one tick (100 ms) of added latency, like a live detector.
    Firing is decided on tick indices, never on raw float seconds, so the replay check and
    the controller can never disagree about a blink that lies exactly on a tick boundary.
    """

    def __init__(self, reverse_at_s: Sequence[float]) -> None:
        self._pending = sorted(reverse_at_s)

    def command(self, time_s: float) -> Command:
        tick = tick_of(time_s)
        fired = False
        # several blinks inside one tick collapse into a single reverse
        while self._pending and tick_of(self._pending[0]) <= tick:
            self._pending.pop(0)
            fired = True
        return Command.REVERSE if fired else Command.NONE

    @property
    def remaining(self) -> int:
        return len(self._pending)


class KeyboardController:
    """Latest arrow / space key wins; fed by :meth:`press` from the event loop."""

    def __init__(self) -> None:
        self._next = Command.NONE

    def press(self, command: Command) -> None:
        self._next = command

    def command(self, time_s: float) -> Command:
        cmd, self._next = self._next, Command.NONE
        return cmd


def tick_of(time_s: float) -> int:
    """Index of the first tick starting at or after ``time_s`` (``ceil(time_s / TICK_S)``).

    The quotient is rounded first so float noise (``1.1 / 0.1 == 11.000000000000002``)
    cannot push an on-boundary time into the next tick.
    """
    return math.ceil(round(time_s / TICK_S, 6))
