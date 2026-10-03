Gnani-SST - Audio Notes Platform (Speech-To-Text)

Upload audio, get a transcript via Gnani ASR, and an LLM summary via Groq.

Stack: Next.js frontend, FastAPI backend, PostgreSQL, Procrastinate jobs,
Cloudflare R2 storage, Docker Compose.

Run locally:
  cp .env.example .env    # fill in the required keys
  docker compose up -d --build

Frontend: http://localhost:3000
Backend API: http://localhost:8000

<img width="1895" height="1069" alt="image" src="https://github.com/user-attachments/assets/3dd6c1a6-738d-4177-b6ae-aa02854e7d68" />
