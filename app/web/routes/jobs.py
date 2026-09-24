"""Job HTTP endpoints: filtered listing."""

from fastapi import APIRouter, Request

from app.discovery.services.filters import parse_filters
from app.discovery.services.job_service import list_jobs
from app.discovery.services.seed import prefill_filters
from app.web.schemas import JobListOut, JobsSettingsOut, job_out

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListOut)
def list_jobs_route(request: Request) -> JobListOut:
    """Stored jobs matching the query-string filters, newest first; 422 bad filter."""
    # Multi-valued: repeated params (?location=EU&location=US) survive getlist,
    # scalars arrive as 1-element lists. Unknown keys are rejected in parse_filters.
    raw = {key: request.query_params.getlist(key) for key in request.query_params}

    filters = parse_filters(raw)  # FilterError -> 422
    jobs, total = list_jobs(filters)

    return JobListOut(jobs=[job_out(job) for job in jobs], total=total)


@router.get("/settings", response_model=JobsSettingsOut)
def jobs_settings_route() -> JobsSettingsOut:
    """Filter prefill: persisted block when present, else seeds from the active resume."""
    return JobsSettingsOut(filters=prefill_filters())
