# Vision — NTXHackathon22, cleaned up

Origin: NeuroTechX Hackathon 2022 (2022-10-29/30). A team (Shuhong Huang, Thomas Mullen,
Marcel Petrick) recorded EEG with an OpenBCI Ganglion to control a one-row Pacman
by brain/eye signals. The hackathon ended with raw recordings, a modified game and an
unrelated notebook — but nobody knew any more what the recordings were or where the
peaks were, so nothing could be trained.

**Goal: a cleaned project in which all tooling is usable, fixed and working.**

## Requirements

### V1 — Clean repository
- Remove junk (`.DS_Store`, macOS `._*` files, committed `__pycache__`, `.idea`).
- Remove the duplicated `data/` tree; keep every unique raw recording, unmodified,
  under `Recordings/`.
- Remove assets that may not be redistributed (the commercial `ALGER.TTF` font).
- Fix the hard-coded `os.chdir("/Users/thomasmullen/...")` in the game.

### V2 — Understand the recordings ("the mystery")
- A machine-readable manifest describing every recording: kind (EEG / impedance /
  blink test), session, start/end time, duration, notes.
- Encode the reconstructed findings: impedance checks misfiled one session off,
  session5 BrainFlow file duplicates the GUI export, no event markers in sessions 2–5,
  `stimulus_order.txt` without timing, the blink file as the only ground truth.

### V3 — Data loading
- Loaders for OpenBCI GUI `.txt`, BrainFlow tab-separated `.csv`, and the
  comma-decimal BrainFlow `.cw` export, plus impedance packets (IDs 201–205).

### V4 — Processing
- Filtering (band-pass, mains notch), signal-quality metrics.
- Blink detection, validated against the blink recording (blinks every 5 s after 10 s).
- Epoching under an explicit, configurable trial-timing hypothesis combined with
  `stimulus_order.txt`, so labelled data for training can be produced once the timing
  is known.
- The notebook's multitaper dynamic spectrum and AR whitening as tested library code,
  applied to our own data (the notebook's `.mat` file is not available).

### V5 — Tools
- A CLI covering inventory, quality, blink detection, epoching, spectrum export,
  web server and game.
- A web UI to browse recordings and see traces, spectrograms, detected blinks and
  impedances (the screenshot in the README comes from it).
- The Pacman game working again: keyboard control and a BCI mode in which blinks
  (replayed from a recording) steer Pacman.
- A runnable notebook that uses the library on our data.
- An automatable **replay check**: feed an existing recording through the analyzer
  into a headless game and verify the outcome (detected blinks vs. ground truth,
  Pacman reacting at the right moments). Reusable in CI and as the e2e baseline for
  continuing where the hackathon stopped.

### V6 — Engineering
- `localPipeline.sh`: format, lint, type check, unit + integration + e2e tests,
  coverage ≥ 95 %, build, docker build + smoke test.
- GitHub Actions mirror the local pipeline; docker image published to GHCR.
- Semver, conventional atomic commits on `main`, every commit bumps the version.
- GPLv3 (keeping the notices of the original MIT/third-party parts).
- README with badges, setup, testing, pipeline, docker and usage docs and a real
  screenshot; documented helper scripts; up-to-date `AGENTS.md`.

### V7 — Ask the team
- A GitHub issue asking the former contributors about the lost Google Doc, the
  stimulus timing and the meaning of `stimulus_order.txt`.
