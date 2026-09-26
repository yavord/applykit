"""In-process discovery worker: claim QUEUED runs, execute, recover (3.5).

One daemon thread per app process polls the DB for QUEUED runs. Correctness
rests on the atomic claim (DiscoveryRepo.claim), never on an in-memory lock,
so any number of processes can safely share one queue. The thread is the only
thing that executes runs at 3.5; the boot catch-up run and the stale-run sweep
run once at startup, before the first poll.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from app.data.models import RunStatus, utcnow
from app.data.repositories import DiscoveryRepo, ResumeRepo
from app.discovery.registry import load_sources
from app.discovery.services.discovery_service import enqueue_run, run_discovery
from app.discovery.source_adapter import SourceAdapter

log = logging.getLogger(__name__)

POLL_INTERVAL = 1.0  # idle seconds between queue polls
STALE_RUN_AGE = timedelta(minutes=15)  # a RUNNING run older than this died with its process
MAX_DATA_AGE = timedelta(hours=24)  # freshness window; shared with the future cron cadence
SHUTDOWN_TIMEOUT = 5.0  # seconds stop() waits for the thread
STALE_MESSAGE = "run interrupted: worker restarted while this run was running"


def recover_stale(now: datetime | None = None, stale_age: timedelta = STALE_RUN_AGE) -> int:
    """Fail RUNNING runs older than stale_age (crash recovery, decision 8)."""
    return DiscoveryRepo().fail_stale((now or utcnow()) - stale_age, STALE_MESSAGE)


def bootstrap_if_stale(
    now: datetime | None = None, max_data_age: timedelta = MAX_DATA_AGE
) -> int | None:
    """Enqueue one catch-up run when data is stale and nothing is pending; else None."""
    runs = DiscoveryRepo()

    if runs.has_unfinished():
        return None

    if ResumeRepo().get_active() is None:
        return None

    if runs.has_ok_completed_since((now or utcnow()) - max_data_age):
        return None

    return enqueue_run()


class DiscoveryWorker:
    """Owns the background thread that executes QUEUED runs."""

    def __init__(
        self,
        run_fn: Callable[[int, Sequence[SourceAdapter]], None] = run_discovery,
        load_fn: Callable[[], list[SourceAdapter]] = load_sources,
        poll_interval: float = POLL_INTERVAL,
        stale_age: timedelta = STALE_RUN_AGE,
        max_data_age: timedelta = MAX_DATA_AGE,
    ) -> None:
        self._run_fn = run_fn
        self._load_fn = load_fn
        self._poll_interval = poll_interval
        self._stale_age = stale_age
        self._max_data_age = max_data_age
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Spawn the daemon poll thread; idempotent."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="discovery-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the thread and join it; never blocks longer than SHUTDOWN_TIMEOUT."""
        self._stop.set()

        if self._thread is not None:
            self._thread.join(SHUTDOWN_TIMEOUT)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run_once(self) -> bool:
        """Claim and execute at most one QUEUED run; False when none was pending."""
        runs = DiscoveryRepo()
        run_id = runs.next_queued()

        if run_id is None:
            return False

        if not runs.claim(run_id):
            return True  # another process/thread won the claim; loop again

        self._execute(runs, run_id)

        return True

    def _execute(self, runs: DiscoveryRepo, run_id: int) -> None:
        """Load the seam, run the orchestration, and never let an exception escape."""
        try:
            self._run_fn(run_id, self._load_fn())
        except Exception as exc:  # SourceConfigError included: it becomes the message
            runs.set_status(run_id, RunStatus.FAILED, message=str(exc) or type(exc).__name__)

    def _loop(self) -> None:
        try:
            recover_stale(stale_age=self._stale_age)  # decision 8 sweep
            bootstrap_if_stale(max_data_age=self._max_data_age)
        except Exception:  # a dead DB must not kill the thread
            log.exception("discovery worker bootstrap failed")

        while not self._stop.is_set():
            try:
                claimed = self.run_once()
            except Exception:
                log.exception("discovery worker tick failed")
                claimed = False

            if not claimed:
                self._stop.wait(self._poll_interval)
