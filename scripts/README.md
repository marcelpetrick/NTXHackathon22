# scripts/

Small, single-purpose helpers. Every script starts with a `# <name> - <purpose>` line
and a usage line; `scripts/check_script_docs.sh` enforces that each one is listed here.

| Script | Purpose |
|---|---|
| `bump_version.sh` | Bump `patch`/`minor`/`major` in `pyproject.toml` and refresh `uv.lock`. |
| `version.sh` | Print the current version. |
| `commit.sh` | Bump version → run `./localPipeline.sh` → commit with a conventional message → push. Stages tracked changes plus the new paths named after `--`; refuses on any other untracked file and commits nothing if the pipeline is red. |
| `check_headers.sh` | Fail if a `.py`/`.sh`/`Dockerfile` lacks an SPDX license header. |
| `check_script_docs.sh` | Fail if a script has no purpose line or is missing from this table. |
| `build_dist.sh` | Build sdist + wheel into `dist/`. |
| `wheel_smoke.sh` | Install the wheel into a temp venv and check `ntxbci --version`. |
| `run_e2e.sh` | Run `pytest -m e2e` (installs Playwright Chromium when needed). |
| `docker_build.sh` | Build `ntxbci:local` and `ntxbci:<version>`. |
| `screenshots.py` | Regenerate the README screenshots (dashboard, blink-test page, game replay) from the running app: `uv run python scripts/screenshots.py`. |
| `make_video.py` | Render the two ≤ 30 s showcase clips of the blink-test replay (EEG next to the game, each blink flying from its spike to Pacman): `explainer` 16:9 real time, `fastcut` 1:1 at 2.6x. Writes `build/video/ntxbci-<cut>.mp4` (+ `.gif` with `--gif`); needs ffmpeg: `uv run python scripts/make_video.py --gif`. The README clip is `--cut explainer --gif --out docs/media`. |
| `docker_smoke.sh` | Run the image, probe `/healthz`, `/api/recordings` and `/`. |
