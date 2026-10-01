# Changelog

## 0.1.0

### Infrastructure

- **f364284**: Project scaffolding — shared root `.gitignore`, backend Dockerfile (uv, non-root,
  `HEALTHCHECK` on `/health`), frontend Dockerfile (Next standalone output on a Node runtime),
  and a `docker compose` stack wiring postgres → backend → frontend.
- **f364284**: `GET /health` on the FastAPI backend.

### Documentation

- **0f54b3d**: `AGENTS.md` — agent guide covering stack, dev commands, architecture, the API
  surface, the Gnani Batch STT flow and conventions for this repo.

### API

- **35245e2**: Stub note routes — `POST /api/notes`, `GET /api/notes`, `GET /api/notes/{id}`,
  `DELETE /api/notes/{id}`, `POST /api/notes/{id}/retry`. Placeholder responses only: no
  persistence, no auth, no storage. Exists so the frontend can be built against the final
  response shapes.