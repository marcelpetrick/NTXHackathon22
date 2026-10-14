# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""FastAPI application factory."""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ntxbci import __version__
from ntxbci.io import electrode_impedance, load_stimulus_order
from ntxbci.manifest import load_manifest, verify
from ntxbci.web.analysis import Analysis, Analyzer
from ntxbci.web.plots import PLOTS, RENDERERS

_HERE = files("ntxbci.web")


def create_app(data_root: Path | str | None = None) -> FastAPI:
    manifest = load_manifest(data_root)
    analyzer = Analyzer(manifest)
    problems = verify(manifest)
    labels = load_stimulus_order(manifest.root / manifest.stimulus_order)

    app = FastAPI(title="ntxbci", version=__version__, docs_url="/api/docs")
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")
    templates = Jinja2Templates(directory=str(_HERE / "templates"))
    templates.env.globals.update(version=__version__, electrode_impedance=electrode_impedance)

    def analysis(entry_id: str) -> Analysis:
        try:
            return analyzer.get(entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown recording {entry_id}") from exc

    @cache
    def plot(entry_id: str, kind: str) -> bytes:
        return RENDERERS[kind](analysis(entry_id))

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "recordings": len(analyzer.recordings())}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        rows = [analysis(e.id) for e in analyzer.recordings()]
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "manifest": manifest,
                "rows": rows,
                "problems": problems,
                "labels": labels,
                "impedances": manifest.by_kind("impedance"),
            },
        )

    @app.get("/recordings/{entry_id}", response_class=HTMLResponse)
    def recording(request: Request, entry_id: str) -> HTMLResponse:
        a = analysis(entry_id)
        return templates.TemplateResponse(request, "recording.html", {"a": a, "plots": PLOTS})

    @app.get("/plots/{entry_id}/{kind}.png")
    def plot_png(entry_id: str, kind: str) -> Response:
        if kind not in RENDERERS:
            raise HTTPException(status_code=404, detail=f"unknown plot {kind}")
        return Response(plot(entry_id, kind), media_type="image/png")

    @app.get("/api/recordings")
    def api_recordings() -> list[dict[str, Any]]:
        return [analysis(e.id).summary() for e in analyzer.recordings()]

    @app.get("/api/recordings/{entry_id}")
    def api_recording(entry_id: str) -> dict[str, Any]:
        return analysis(entry_id).details()

    @app.get("/api/replay/{entry_id}")
    def api_replay(entry_id: str) -> dict[str, Any]:
        return analysis(entry_id).replay.to_dict()

    @app.get("/api/manifest")
    def api_manifest() -> dict[str, Any]:
        return {
            "device": manifest.device,
            "notes": list(manifest.notes),
            "stimulus_order": labels,
            "problems": problems,
        }

    return app
