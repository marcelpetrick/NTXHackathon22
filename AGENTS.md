# AGENTS.md

Context for AI coding agents (and humans) working in this repository.

## What this is

Leftovers from the **NTX Hackathon 2022** (recorded 2022-10-29/30, CEST). The goal was
a brain–computer interface: control a stripped-down **Pacman** game with EEG recorded
from an **OpenBCI Ganglion** (4 EXG channels, 200 Hz, BLE). The project never got to
the point of a trained classifier; there is no pipeline connecting the recordings to
the game.

Contributors (see `.mailmap`): Shuhong Huang (GitHub `Timbrer`, repo owner),
Thomas Mullen, Marcel Petrick.

The README links a Google Doc with the team notes; as of 2026-10 it returns
**HTTP 410 Gone** — the experiment protocol is effectively lost.

## Layout

| Path | Content |
|---|---|
| `pacman/` | Pygame Pacman (third-party original, commit `417418c`), reduced to a single-row level 606×86 px (`f374c4a`). Keyboard only, no BCI input. |
| `Recordings/` | Evening EEG sessions 2–5 + `stimulus_order.txt`. |
| `data/` | Byte-identical copy of `Recordings/OpenBCISession_session{2..5}` (session2 without the `_possibly_mislabeled` suffix) **plus** the only labelled recording, the blink file. |
| `get_dynamic_spectrum.ipynb` | Multitaper dynamic spectrum + AR whitening. Loads `ws_data_1shank.mat` (16-ch hippocampal LFP @1250 Hz) — workshop sample data, **not in the repo and not our EEG**. Never applied to the Ganglion data. |

## Data formats

- `OpenBCI-RAW-*.txt` — OpenBCI GUI export. 4 `%` header lines + column header, comma
  separated. Columns: `0` sample index (wraps 0–100 or 0–200), `1–4` EXG ch0–3 (µV),
  `5–7` accelerometer X/Y/Z (Z ≈ 1 g; **not markers**), `8–12` "Other" (zero),
  `13` unix timestamp, `14` other, `15` formatted timestamp.
- `BrainFlow-RAW_*.csv` — BrainFlow export, tab separated, same column order, no header.
- `data/blinking…csv/…csv_0.cw` — BrainFlow format but with **comma as decimal
  separator** (German locale) and every sample index appearing twice.
- `Recordings/…session2…/._OpenBCI-RAW…txt` and `.DS_Store` are macOS metadata junk.

## What each recording actually is (reconstructed 2026-10-14)

| Recording | Time (CEST) | Length | Notes |
|---|---|---|---|
| `session2` EEG | 20:35:18–20:38:13 | 175 s | Large artefacts at ~67, 109, 128 s. |
| `session3` EEG | 20:39:45–20:42:32 | 167 s | Artefacts 17–20 s. |
| `session4` EEG | 20:46:01–20:48:51 | 170 s | Weak ~12 s periodicity in artefact envelope. |
| `session5` EEG | 20:49:33–20:52:28 | 175 s | `BrainFlow-RAW_session5_1.csv` is the same stream (identical data). |
| `BrainFlow-RAW_session{2,3,4}_1.csv` | 20:39:36 / 20:45:50 / 20:49:13 | 6–13 s | **Impedance checks**, not EEG: packet IDs 201–205, cols 8–12 = per-electrode impedance (kΩ: ch1–4 + ref). Each was taken *before the next* session, so the file in folder N belongs to session N+1 — likely the "possibly mislabeled" confusion. |
| blink file | 2022-10-30 12:45:22, 58 s | | Eyes-blink test: no blink for 10 s, then one every 5 s. Blink peaks verified at ≈10, 15, 20, 25, 29, 35, 40, 45, 50, 54 s. **The only recording with known event times.** |
| deleted in `f1374da` (`OpenBCISession_2022-10-29_14-06-41` … `16-07-01`) | 14:06–16:10 | 0.3 s – 17 min | Afternoon setup/trial runs. Channel std 5 000–14 000 µV vs. 50–190 µV in the evening → bad electrode contact. Recoverable via `git show f1374da^:<path>`. |

### The open problem: no event markers

Sessions 2–5 contain **no trigger/marker channel** (the non-zero aux columns are only
the accelerometer). `Recordings/stimulus_order.txt` lists 14 binary stimuli
(`1 1 1 1 0 1 0 0 0 1 1 0 0 0`) but nothing records *when* each stimulus started, what
`0`/`1` mean, or which session(s) it applies to. 14 trials × ~12 s ≈ 168 s matches the
session lengths, and session4 shows a weak 12 s periodicity, but that is a hypothesis,
not ground truth. Consequently the sessions cannot be epoched or used to train a
classifier as-is. Any analysis must state its assumed trial timing explicitly.

## Running things

No dependency manifest exists. Inferred: Python 3.8, `pygame` (game),
`numpy scipy matplotlib` (notebook/analysis).

- `pacman/pacman.py` hard-codes `os.chdir("/Users/thomasmullen/…/pacman")` (from
  `0453637`); remove/replace it or run from `pacman/` with that line patched.
- Arrow keys move; ENTER restarts, ESC quits.

## Conventions / cautions for agents

- Raw recordings are the historical record: **do not modify, reformat or delete** them.
  Write derived data/scripts elsewhere.
- `data/` and `Recordings/` duplicate each other; if de-duplicating, keep
  `Recordings/` and move the blink file there.
- `pacman/__pycache__/` and `.DS_Store` are committed despite `.gitignore`; safe to
  `git rm --cached`.
- Code style in `pacman/`: tabs, `'''docstring'''` comments above functions.
