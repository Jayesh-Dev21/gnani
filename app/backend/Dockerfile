FROM python:3.11-slim-bookworm AS builder

ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv

WORKDIR /srv

COPY pyproject.toml uv.lock .python-version README.md ./

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH"

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin app

WORKDIR /srv

COPY --from=builder --chown=app:app /srv/.venv /srv/.venv
COPY --from=builder --chown=app:app /srv/README.md /srv/README.md
COPY --chown=app:app src ./src
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations

RUN mkdir -p /srv/data && chown app:app /srv/data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]