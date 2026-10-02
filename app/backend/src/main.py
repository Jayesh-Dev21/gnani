from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import settings
from src.db.models import Base  # noqa: F401  (registers tables for Alembic)
from src.modules.notes.router import router as notes_router

app = FastAPI(title="Audio Notes API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first.get("loc", [])[1:])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": f"{field}: {first.get('msg')}" if field else first.get("msg")},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "audio-notes-api", "version": "0.1.0"}