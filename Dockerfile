# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# ntxbci dashboard + CLI. The recordings are baked in at /data (34 MB).
#   docker run --rm -p 8000:8000 ghcr.io/marcelpetrick/ntxhackathon22
#   docker run --rm ghcr.io/marcelpetrick/ntxhackathon22 ntxbci replay blink-test

FROM ghcr.io/astral-sh/uv:0.12-python3.14-trixie-slim AS build
WORKDIR /src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY LICENSES ./LICENSES
COPY src ./src
# runtime dependencies pinned by uv.lock, then the freshly built wheel
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /tmp/requirements.txt \
 && uv build --wheel --out-dir /dist \
 && uv venv /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache -r /tmp/requirements.txt \
 && VIRTUAL_ENV=/opt/venv uv pip install --no-cache --no-deps /dist/*.whl

FROM python:3.14-slim-trixie
LABEL org.opencontainers.image.source="https://github.com/marcelpetrick/NTXHackathon22" \
      org.opencontainers.image.description="NTX Hackathon 2022 BCI toolkit: recordings dashboard, blink detection and replay check" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
RUN useradd --create-home --uid 10001 ntx
COPY --from=build /opt/venv /opt/venv
COPY Recordings /data
ENV PATH="/opt/venv/bin:$PATH" NTXBCI_DATA=/data MPLBACKEND=Agg MPLCONFIGDIR=/tmp/mpl PYTHONUNBUFFERED=1
USER ntx
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["ntxbci", "serve", "--host", "0.0.0.0", "--port", "8000"]
