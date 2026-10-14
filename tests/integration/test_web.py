# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""HTTP-level tests of the dashboard (FastAPI TestClient)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ntxbci.web import create_app

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def client(mini_dataset: Path) -> TestClient:
    return TestClient(create_app(mini_dataset))


def test_openapi_docs(client: TestClient) -> None:
    assert "swagger" in client.get("/api/docs").text.lower()
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/recordings/{entry_id}" in paths


def test_health(client: TestClient) -> None:
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["recordings"] == 2


def test_index_lists_recordings(client: TestClient) -> None:
    html = client.get("/").text
    assert "What did we record?" in html
    assert 'href="/recordings/blink"' in html
    assert "all files verified" in html
    assert "imp-s1" in html


def test_recording_page_and_plots(client: TestClient) -> None:
    html = client.get("/recordings/s1").text
    assert "Channel quality" in html
    assert "Impedance before this session" in html
    for kind in ("traces", "blinks", "spectrogram"):
        r = client.get(f"/plots/s1/{kind}.png")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content.startswith(PNG_MAGIC)
    assert client.get("/plots/blink/traces.png").content.startswith(PNG_MAGIC)
    blink_html = client.get("/recordings/blink").text
    assert "Detection vs. protocol: 3/3" in blink_html


def test_api(client: TestClient) -> None:
    rows = client.get("/api/recordings").json()
    assert {r["id"] for r in rows} == {"s1", "blink"}
    detail = client.get("/api/recordings/s1").json()
    assert len(detail["channels"]) == 4
    assert detail["impedance_kohm"] == {
        "ch1": 18.5,
        "ch2": 17.5,
        "ch3": 23.5,
        "ch4": 8.0,
        "ref": 14.0,
    }
    assert client.get("/api/recordings/blink").json()["impedance_kohm"] is None
    assert client.get("/api/replay/blink").json()["passed"] is True
    manifest = client.get("/api/manifest").json()
    assert manifest["stimulus_order"] == [1, 0, 1, 1]
    assert manifest["problems"] == []


@pytest.mark.parametrize(
    "url", ["/recordings/nope", "/recordings/imp-s1", "/plots/s1/nope.png", "/api/replay/nope"]
)
def test_not_found(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == 404


def test_problem_banner(mini_dataset: Path) -> None:
    (mini_dataset / "stray.txt").write_text("x", encoding="utf-8")
    html = TestClient(create_app(mini_dataset)).get("/").text
    assert "1 problem(s)" in html


def test_real_dashboard(real_root: Path) -> None:
    client = TestClient(create_app(real_root))
    rows = {r["id"]: r for r in client.get("/api/recordings").json()}
    assert set(rows) == {
        "session2",
        "session3",
        "session4",
        "session5",
        "session5-brainflow",
        "blink-test",
    }
    assert rows["blink-test"]["blinks"] == 10
    assert all(r["replay_passed"] for r in rows.values())
