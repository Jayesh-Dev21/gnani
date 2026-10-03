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

### UI

- Theme toggle is now a sun/moon icon instead of LIGHT/DARK text.
- "New recording" opens an empty dashboard: transcript area cleared, composer back in the tray.
- The bottom tray doubles as the playback bar once a transcript is open — the upload controls are
  useless there, so the tray shows the note title, status and the audio player instead.

### UI

- The audio player blends into the page: transparent background, no grey box, tabular mono
  timecodes in both themes.
- `/architecture` rewritten to describe what is actually built: Better Auth with JWT verification
  through JWKS, per-user scoping and 404-instead-of-403, Postgres persistence, local-disk storage
  behind one module, the queue decision, and an explicit section on what is still stubbed.

### UI

- Replaced the native audio element with a custom player: play/pause, seek and volume sliders,
  tabular mono timecode. Chromium paints its own control panel and will not blend it with the
  page, so the controls are ours now and follow the theme in both light and dark.

### UI

- The volume slider is hidden until you hover the volume region (or tab into it), so the tray
  shows just the speaker icon at rest. Tailwind gates `hover:` behind `@media (hover: hover)`,
  which is why the expansion only appears on pointer devices.

### Configuration

- `GNANI_API_KEY` (required), `GNANI_MODEL` and `STT_REST_TIMEOUT_SECONDS` placeholders in
  `.env.example`; the backend refuses to start when the key is blank.
- `app/backend/.env.example` documents every backend setting, including the `AUTH_JWKS_URL` that
  must point at the `frontend` service inside compose and the audience that must match
  `BETTER_AUTH_URL`.
- Compose gained a `migrate` service so Better Auth's tables are applied automatically, and the
  backend derives the asyncpg driver from the shared `DATABASE_URL`.

### Fixes

- The `migrate` compose service ran the frontend's runtime image, which is node-only
  (standalone output) and has no `bun` or `drizzle-kit`. It now builds from a dedicated `migrate`
  stage carrying bun, `node_modules`, `drizzle.config.ts`, the schema and the migration folder, so
  `docker compose up -d` applies Better Auth's tables on a clean machine instead of failing with
  `Cannot find module '/srv/bun'`.

### Features

- Transcription now runs as a queued job instead of inside the upload request.
  `POST /api/notes` writes a `queued` note and returns; a `worker` service
  (same image, `python -m src.worker`) claims it, writes `transcribing`, runs
  Gnani, then writes `ready` or `failed`. Procrastinate on Postgres is the queue,
  so there is no second service to operate. Queue schema is installed by the
  backend's start command, migrations stay in Alembic.
- Gnani integration in `src/modules/transcription/gnani.py`: try the synchronous
  `POST /stt/v3` endpoint, escalate to Batch STT when Gnani reports the audio is
  over its 60 second cap, then poll at 30s, list completed files and download
  `full_transcript`. A 429 from polling, `/start`, or the file listing is waited
  out rather than reported as a failure, and a reattached job found in `CREATED`
  is started, since creating a job does not start it.
- No automatic retries, because a retry after a crash would re-send audio Gnani
  has already billed. Instead every attempt takes a lease on the note
  (`attempt_id`, `lease_expires_at`) and records the provider job it created
  (`provider_job_id`, `provider_submitted_at`). On worker start, notes with an
  expired lease go back to `queued` and are re-deferred with the provider job id
  intact, so the next attempt resumes the same Gnani job instead of paying twice.
  `POST /api/notes/{id}/retry` now accepts a `queued` note too, which is the only
  way to rescue a note whose job died before it was claimed.
- The UI polls the note list every 3 seconds while any note is `queued` or
  `transcribing`, re-reads the open note when its status changes, shows what each
  in-flight state means, and offers Retry on a failed note with the provider's own
  message instead of an error code.

### Changes

- Duration is now read in the browser the moment a file is picked, using an
  object URL and a metadata-only `<audio>` read (`lib/audio-meta.ts`), and sent
  with the upload. The note therefore knows how long the recording is before
  transcription finishes, instead of only after Gnani answers. The server
  sanitises the value (finite, positive, under four hours) and the worker still
  overwrites it with the provider's own figure when the transcript arrives.
- English is the default language, on both sides: the composer's select starts
  on `en-IN` and `DEFAULT_LANGUAGE_CODE` is `en-IN` rather than a Hindi-first
  list. The duration is shown in the composer's file line and in a note's
  details.
- A failed note's retry affordance is now a `↻` glyph beside its details, and the
  duplicate Retry button in the action row is gone.

### Features

- Summarisation via GroqCloud, as its own queued job (`summarise_note`) rather than a chained
  step, so a provider outage never disturbs a transcript that already succeeded and a summary can
  be retried on its own. `summarising` joins the status set; the note passes through it and lands
  back on `ready`. A summary failure leaves the transcript exactly as it was.
- `src/modules/summarisation/llm.py` holds the fallback chain: models are tried in the order
  `GROQ_MODELS` lists them (`openai/gpt-oss-120b` → `qwen/qwen3.8-27b` → `openai/gpt-oss-20b`).
  429, 5xx, timeouts, transport errors and empty completions move to the next model; a 401/403/400
  raises immediately with the provider's own message so a wrong key is not hidden behind two more
  attempts. After two consecutive transient failures a model is benched for
  `LLM_MODEL_COOLDOWN_SECONDS`, so an outage costs one note one skipped attempt rather than three
  failed calls per note, and every model benched reports "temporarily unavailable" instead of
  retrying into the same wall.
- Long transcripts are summarised chunk by chunk on paragraph boundaries and the partial summaries
  are reduced into one answer, so a multi-hour Batch recording is never truncated at the tail.
  `reasoning_effort` is sent only to the `openai/gpt-oss` family, which documents it.
- `POST /api/notes/{id}/retry` now re-runs the step that actually failed: a note that has a
  transcript retries only its summary, so pressing Retry never pays for transcription twice.
- Startup recovery understands `summarising` as well as `transcribing`, and `GROQ_API_KEY` is
  required at startup for the same reason `GNANI_API_KEY` is: a missing provider key is a
  configuration failure, not a per-request surprise.

### Features

- Cloudflare R2 as the production audio backend, behind the existing storage
  interface: `STORAGE_BACKEND=local` keeps writing under `DATA_DIR` and
  `STORAGE_BACKEND=r2` uses the bucket's S3-compatible API over `aioboto3`. An
  upload is spooled to a temporary file first, so the size limit is still enforced
  while the bytes arrive and the bucket gets a file to send instead of a buffer.
  Switching backends changes no other code.
- The R2 bucket is private. `audio_url` becomes a short-lived presigned GET URL
  (one hour, matching Gnani's own link lifetime), the browser hands that straight
  to the `<audio>` element instead of proxying bytes through the API, and the
  authenticated `/api/notes/{id}/audio` route answers with a 307 to a signed URL
  so anything holding the old path keeps working. A leaked URL now expires rather
  than staying a permanent public file.
- Batch STT switches to `source: {type: "cloud_storage"}` when audio lives in R2,
  so Gnani fetches the object itself and the 10MB per-file multipart cap stops
  applying. The synchronous endpoint still needs real bytes, so that path downloads
  to a temporary file first, and the file is released before the job starts
  polling.
- Object metadata no longer lives in a `meta.json` sidecar. The database already
  had filename, content type and size, and a sidecar could not work for a bucket
  anyway, so the audio route reads the note row and the sidecar is gone.
- A failed note keeps its transcript when only the summary failed, and the reload
  glyph beside a note's details is offered whenever there is something to
  regenerate: a failed step, or a ready note whose summary never arrived. Its
  label follows the step, "Regenerate summary" once a transcript exists and
  "Retry transcription" before that.

### Features

- Audio lives only in Cloudflare R2 now. The local-disk backend, the `meta.json`
  sidecar, the authenticated streaming route and the `audio_data` volume are gone;
  `src/storage.py` speaks to the bucket and nothing else knows where bytes live.
  Verified against the real bucket: upload, byte-identical download, presigned URL
  and delete all round-trip.
- A reload glyph on a note's details asks Gnani for another transcript of the same
  file, and every pass is kept in a new `transcript_iterations` table rather than
  overwriting the last one. A failed pass is recorded as a failure and leaves any
  earlier successful transcript in place, so a retry can never lose work that
  already succeeded. `POST /api/notes/{id}/retry` takes an optional `target` of
  `transcription` or `summary`; omitting it infers the step from the note's state.
  An explicit `transcription` request forgets the previous provider job on purpose,
  because resuming it would hand back identical text, while an inferred retry keeps
  it so a live Gnani job is never paid for twice.
- Recovery now sweeps on a timer instead of only at startup, so a note abandoned by
  a worker that crashed long after boot is reclaimed on its own. A note left in a
  non-terminal state with no lease at all is reclaimed too; that state was previously
  invisible to the sweep and could only be cleared by restarting the worker.
- `deploy/setup-nginx.sh` and `deploy/nginx.conf` put nginx in front of the stack on
  a single EC2 instance: TLS terminated at the edge, `/` to the frontend, `/api/` to
  the backend, request and response buffering off so uploads stream and Range
  requests pass through untouched. `deploy/setup-ec2.sh` prepares a fresh Ubuntu
  instance with Docker, log rotation, swap and the first compose run.

### Fixes

- Playback on object storage built `http://localhost:8000https://…` because the API
  base was glued onto an already absolute signed URL. `audioUrl` and `fetchAudio`
  now pass an absolute URL through untouched.
- Audio is streamed to the browser by the API again, out of R2, with Range support,
  instead of being handed over as a presigned link. R2 itself was never the problem,
  so the bucket stays private: a cross-origin grant, a link that expires mid-session
  and a fresh signature on every poll restarting the player's buffer were three
  separate ways for playback to break, and the hop removes all three. Verified
  against the real bucket: 200 for the whole file byte-identical to the upload, 206
  with a correct `content-range` for a range request, 401 without a token.
- Gnani Batch submissions sent a form-encoded body with no file part, which the API
  rejects as invalid JSON, and then a `cloud_storage` source it cannot fulfil for R2.
  Both endpoints now receive the bytes, downloaded from R2 once into a temporary
  file that is released before polling starts.

### Fixes

- **9e896fc**: A re-transcribed note kept the old transcript's summary;
  `_mark_ready` now clears it and the summary job re-runs against the new pass.
- **9e896fc**: Audio duration showed garbage (21:32) and did not play for raw ADTS
  AAC / AMR uploads; the audio route now transcodes those to mp3, direct-serves
  browser-ready containers with Range, and uploads are probed with ffprobe.
- **9e896fc**: Architecture page stale sections removed, diagram arrows corrected,
  Punjabi/Gujarati batch support, live transcript and segment time indexing added
  to the roadmap.
