"""API router registry: every domain router registers here under /api."""

from fastapi import APIRouter

from app.web.routes.resumes import router as resumes_router

api_router = APIRouter(prefix="/api")

api_router.include_router(resumes_router)
