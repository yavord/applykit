"""FastAPI app entry: error mapping, API routers, static SPA mount."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.discovery import FilterError
from app.resumes import ExtractionError, UnsupportedFormatError
from app.resumes.errors import ResumeError
from app.web.router import api_router

app = FastAPI()

app.include_router(api_router)


@app.exception_handler(FilterError)
async def filter_error_handler(request, exc: FilterError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(ResumeError)
async def resume_error_handler(request, exc: ResumeError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(UnsupportedFormatError)
async def unsupported_format_handler(request, exc: UnsupportedFormatError) -> JSONResponse:
    return JSONResponse(status_code=415, content={"detail": str(exc)})


@app.exception_handler(ExtractionError)
async def extraction_error_handler(request, exc: ExtractionError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# Mount LAST so /api wins; skip while the SPA is not built (a missing dir
# would 500 every request despite check_dir=False).
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
