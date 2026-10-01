from fastapi import FastAPI

from src.modules.notes.router import router as notes_router

app = FastAPI(title="Audio Notes API", version="0.1.0")

app.include_router(notes_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "audio-notes-api", "version": "0.1.0"}