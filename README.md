gnani - Audio Notes Platform

Upload audio, get a transcript via Gnani ASR, and an LLM summary via Groq.

Stack: Next.js frontend, FastAPI backend, PostgreSQL, Procrastinate jobs,
Cloudflare R2 storage, Docker Compose.

Run locally:
  cp .env.example .env    # fill in the required keys
  docker compose up -d --build

Frontend: http://localhost:3000
Backend API: http://localhost:8000
