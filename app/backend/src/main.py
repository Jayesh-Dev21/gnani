from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.modules.notes.router import router as notes_router

app = FastAPI(title="Audio Notes API", version="0.1.0")

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