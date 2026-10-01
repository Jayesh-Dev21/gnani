from fastapi import FastAPI

app = FastAPI(title="Audio Notes API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "audio-notes-api", "version": "0.1.0"}