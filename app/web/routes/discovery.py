"""Discovery run HTTP endpoints: enqueue, poll, latest."""

from fastapi import APIRouter

from app.discovery.filters import save_filters
from app.discovery.services.discovery_service import enqueue_run, get_run, latest_run
from app.web.schemas import DiscoveryRunIn, RunOut, run_out

router = APIRouter(prefix="/discovery-runs", tags=["discovery"])


@router.post("", status_code=201, response_model=RunOut)
def create_run_route(payload: DiscoveryRunIn | None = None) -> RunOut:
    """Queue a run for the active resume; 422 bad filters, 409 no active resume.

    Submitted filters are validated and persisted first (so 422 wins over 409),
    then the run snapshots the active resume, its revision, and the source list.
    """
    block = save_filters(payload.filters) if payload and payload.filters is not None else None

    return run_out(*get_run(enqueue_run(filters=block)))


@router.get("/latest", response_model=RunOut | None)
def latest_run_route() -> RunOut | None:
    """Newest run with per-source states, or null when nothing ever ran."""
    found = latest_run()

    return None if found is None else run_out(*found)


@router.get("/{run_id}", response_model=RunOut)
def get_run_route(run_id: int) -> RunOut:
    """One run with per-source states and aggregates; 404 unknown id."""
    return run_out(*get_run(run_id))
