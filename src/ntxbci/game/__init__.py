# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""One-row Pacman, controllable by keyboard or by (replayed) blinks.

Rewrite of the hackathon's modified CharlesPikachu/Games Pacman. The rules live in the
pure :mod:`ntxbci.game.model`; :mod:`ntxbci.game.render` and :mod:`ntxbci.game.app`
add pygame on top, so the game logic is testable and replayable without a display.
"""
