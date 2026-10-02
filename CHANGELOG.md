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
### Security

- Notes are now owned by a user. FastAPI verifies the Better Auth session JWT against the
  published JWKS (`X-Anonymous` style header guessing is no longer possible), scopes every query
  by the verified user id, and returns `404` for another user's note or audio.
- The saved-transcript list moved out of `localStorage` and into Postgres. Two accounts on one
  machine no longer share transcripts.

### API

- Real persistence: `notes` table via SQLAlchemy 2.0 async and an Alembic migration, with
  `user_id`, status, transcript, summary and error columns.
- Added `PATCH /api/notes/{id}` for renaming, user-scoped `GET /api/notes`, and range streaming
  for `GET /api/notes/{id}/audio`.
- Better Auth gains the `jwt` plugin plus its `jwks` table, and `BETTER_AUTH_TRUSTED_ORIGINS` so
  `127.0.0.1` and LAN origins are accepted like `localhost`.
- CORS origins, dev-auth guard (`ENABLE_DEV_AUTH` refuses to start under `ENV=production`),
  audio fetched with the session token so the player can use it.
