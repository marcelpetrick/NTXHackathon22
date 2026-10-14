# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""ntxbci - tools for the NTX Hackathon 2022 Ganglion recordings and the blink Pacman."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from ntxbci import __version__
from ntxbci.epochs import TrialTiming, fit_timing, make_epochs, scan_timing
from ntxbci.events import BlinkParams, detect_blinks, match_events
from ntxbci.io import load_recording, load_stimulus_order
from ntxbci.manifest import Manifest, load_manifest, verify
from ntxbci.processing import clean, quality
from ntxbci.replay import replay
from ntxbci.spectral import dynamic_spectrum


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


def _manifest(args: argparse.Namespace) -> Manifest:
    return load_manifest(args.data)


def _range(spec: str) -> list[float]:
    """``start:stop:step`` (inclusive stop) or a single number."""
    parts = [float(p) for p in spec.split(":")]
    if len(parts) == 1:
        return parts
    if len(parts) != 3 or parts[2] <= 0:
        raise argparse.ArgumentTypeError(f"expected start:stop:step, got {spec!r}")
    start, stop, step = parts
    return [round(v, 6) for v in np.arange(start, stop + step / 2, step)]


def cmd_inventory(args: argparse.Namespace) -> int:
    m = _manifest(args)
    problems = verify(m)
    if args.json:
        _print_json(
            {
                "device": m.device,
                "notes": list(m.notes),
                "recordings": [asdict(e) for e in m.entries],
                "problems": problems,
            }
        )
    else:
        print(f"{m.device}\n")
        print(f"{'id':28} {'kind':11} {'start':25} {'dur[s]':>7}  notes")
        for e in m.entries:
            dur = f"{e.duration_s:7.1f}" if e.duration_s is not None else "      -"
            print(f"{e.id:28} {e.kind:11} {e.start.isoformat():25} {dur}  {e.notes[:60]}")
        print("\nnotes:")
        for note in m.notes:
            print(f"  - {note}")
        print(f"\nmanifest check: {'OK' if not problems else 'PROBLEMS'}")
        for p in problems:
            print(f"  ! {p}")
    return 1 if problems else 0


def cmd_quality(args: argparse.Namespace) -> int:
    m = _manifest(args)
    rec = load_recording(m.file(m.get(args.id)))
    q = quality(rec)
    if args.json:
        _print_json([asdict(c) for c in q])
    else:
        print(f"{args.id}: {rec.duration:.1f}s @ {rec.fs:.0f} Hz")
        for c in q:
            print(
                f"  ch{c.channel + 1}: {c.status:5} std={c.std_uv:7.1f}uV "
                f"artefacts={c.artefact_fraction:6.1%} line-noise={c.line_noise_ratio:6.1f}x"
            )
    return 0


def cmd_blinks(args: argparse.Namespace) -> int:
    m = _manifest(args)
    entry = m.get(args.id)
    params = BlinkParams(threshold_z=args.threshold)
    blinks = detect_blinks(load_recording(m.file(entry)), params)
    out: dict[str, Any] = {"blinks": [asdict(b) for b in blinks]}
    if entry.events is not None:
        r = match_events([b.time_s for b in blinks], entry.events.times_s, entry.events.tolerance_s)
        out["ground_truth"] = {
            "precision": r.precision,
            "recall": r.recall,
            "f1": r.f1,
            "mean_latency_s": r.mean_latency_s,
            "missed_s": r.false_negatives,
            "spurious_s": r.false_positives,
        }
    if args.json:
        _print_json(out)
    else:
        print(f"{len(blinks)} blinks in {args.id}:")
        for b in blinks:
            print(f"  {b.time_s:8.2f}s  z={b.strength_z:6.1f}")
        if "ground_truth" in out:
            gt = out["ground_truth"]
            print(
                f"ground truth: precision={gt['precision']:.2f} recall={gt['recall']:.2f} "
                f"F1={gt['f1']:.2f} latency={gt['mean_latency_s']:+.2f}s"
            )
    return 0


def _timing(args: argparse.Namespace, duration: float, n: int) -> TrialTiming:
    if args.trial is not None:
        return TrialTiming(args.onset, args.trial)
    return fit_timing(duration, n, args.onset)


def cmd_epochs(args: argparse.Namespace) -> int:
    m = _manifest(args)
    rec = load_recording(m.file(m.get(args.id)))
    labels = load_stimulus_order(m.root / m.stimulus_order)
    timing = _timing(args, rec.duration, len(labels))
    ep = make_epochs(rec, labels, timing)
    np.savez_compressed(
        args.out,
        data=ep.data,
        labels=np.array(ep.labels),
        onsets_s=np.array(ep.onsets_s),
        fs=ep.fs,
        hypothesis=json.dumps(asdict(timing)),
    )
    print(
        f"wrote {args.out}: {ep.data.shape[0]} epochs x {ep.data.shape[1]} samples x "
        f"{ep.data.shape[2]} channels, ASSUMED timing onset={timing.onset_s}s "
        f"trial={timing.trial_s:.3f}s"
    )
    return 0


def cmd_scan_timing(args: argparse.Namespace) -> int:
    m = _manifest(args)
    rec = load_recording(m.file(m.get(args.id)))
    labels = load_stimulus_order(m.root / m.stimulus_order)
    scores = scan_timing(rec, labels, args.onsets, args.lengths)[: args.top]
    if args.json:
        _print_json([{**asdict(s.timing), "accuracy": s.accuracy} for s in scores])
    else:
        print(f"LOO accuracy per timing hypothesis ({len(labels)} trials, chance ~0.5):")
        for s in scores:
            print(
                f"  onset={s.timing.onset_s:6.2f}s trial={s.timing.trial_s:6.2f}s  {s.accuracy:.2f}"
            )
        print("exploratory only - 14 trials cannot establish the real timing")
    return 0


def cmd_spectrum(args: argparse.Namespace) -> int:
    m = _manifest(args)
    rec = load_recording(m.file(m.get(args.id)))
    x = clean(rec)[:, args.channel - 1]
    ds = dynamic_spectrum(x, rec.fs, nperseg=args.nperseg).band(args.fmin, args.fmax)
    with Path(args.out).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["time_s", *[f"{f:.2f}" for f in ds.freqs_hz]])
        for t, row in zip(ds.times_s, ds.power, strict=True):
            writer.writerow([f"{t:.3f}", *[f"{v:.6g}" for v in row]])
    print(f"wrote {args.out}: {len(ds.times_s)} segments x {len(ds.freqs_hz)} frequencies")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    m = _manifest(args)
    report = replay(m, args.id, BlinkParams(threshold_z=args.threshold), min_f1=args.min_f1)
    if args.json:
        _print_json(report.to_dict())
    else:
        print(f"replay {report.recording}: {len(report.blinks_s)} blinks -> game")
        if report.detection is not None:
            d = report.detection
            print(
                f"  detection: {d.detected}/{d.expected} F1={d.f1:.2f} "
                f"latency={d.mean_latency_s:+.2f}s missed={list(d.missed_s)} "
                f"spurious={list(d.spurious_s)}"
            )
        g = report.game
        print(
            f"  game: {g.status} score={g.score} lives={g.lives} t={g.duration_s:.1f}s "
            f"turns={g.turns} (blinks applied {g.blinks_applied}, after end {g.blinks_after_end})"
        )
        print(f"  deterministic: {report.deterministic}")
        print("PASS" if report.passed else "FAIL")
        for p in report.problems:
            print(f"  ! {p}")
    if args.play or args.screenshot:
        seconds = m.get(args.id).duration_s or 60.0
        _play_window(list(report.blinks_s), args, f"replay {args.id}", seconds)
    return 0 if report.passed else 1


def _play_window(
    blinks: list[float] | None, args: argparse.Namespace, caption: str, seconds: float
) -> None:
    from ntxbci.game.app import RunOptions, run  # noqa: PLC0415 - pygame is an optional extra
    from ntxbci.game.controllers import (  # noqa: PLC0415
        Controller,
        KeyboardController,
        ScriptedController,
    )

    controller: Controller = KeyboardController() if blinks is None else ScriptedController(blinks)
    options = RunOptions(
        realtime=not args.headless,
        speed=args.speed,
        max_seconds=seconds,
        time_limit_s=seconds,
        screenshot=Path(args.screenshot) if args.screenshot else None,
        caption=caption,
        headless=args.headless,
    )
    state = run(controller, options)
    print(f"game over: {state.status.value} score={state.score} t={state.time_s:.1f}s")


def cmd_play(args: argparse.Namespace) -> int:
    _play_window(None, args, "arrows/space, ESC quits", args.seconds)
    return 0


def _game_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--speed", type=float, default=1.0, help="real-time speed factor")
    p.add_argument("--headless", action="store_true", help="no window, not real time")
    p.add_argument("--screenshot", metavar="PNG", help="save the last frame")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ntxbci", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="recordings folder (default: $NTXBCI_DATA or ./Recordings)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inventory", help="list recordings and verify the manifest")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("quality", help="per-channel signal quality")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_quality)

    p = sub.add_parser("blinks", help="detect blinks (and score against ground truth)")
    p.add_argument("id")
    p.add_argument("--threshold", type=float, default=BlinkParams().threshold_z)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_blinks)

    p = sub.add_parser("epochs", help="export labelled epochs (.npz) under a timing hypothesis")
    p.add_argument("id")
    p.add_argument("--onset", type=float, default=0.0, help="first trial onset [s]")
    p.add_argument("--trial", type=float, default=None, help="trial length [s] (default: fill)")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_epochs)

    p = sub.add_parser("scan-timing", help="compare trial-timing hypotheses (exploratory)")
    p.add_argument("id")
    p.add_argument("--onsets", type=_range, default=_range("0:10:1"), help="start:stop:step")
    p.add_argument("--lengths", type=_range, default=_range("10:12.5:0.5"), help="start:stop:step")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan_timing)

    p = sub.add_parser("spectrum", help="export a multitaper dynamic spectrum as CSV")
    p.add_argument("id")
    p.add_argument("--channel", type=int, default=1, choices=range(1, 5))
    p.add_argument("--nperseg", type=int, default=256)
    p.add_argument("--fmin", type=float, default=1.0)
    p.add_argument("--fmax", type=float, default=40.0)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_spectrum)

    p = sub.add_parser("replay", help="recording -> blink detector -> game check")
    p.add_argument("id")
    p.add_argument("--threshold", type=float, default=BlinkParams().threshold_z)
    p.add_argument("--min-f1", type=float, default=1.0)
    p.add_argument("--json", action="store_true")
    p.add_argument("--play", action="store_true", help="also show the replay in a window")
    _game_args(p)
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("play", help="play the game with the keyboard")
    _game_args(p)
    p.add_argument("--seconds", type=float, default=120.0, help="survive this long to win")
    p.set_defaults(func=cmd_play)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        code: int = args.func(args)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
