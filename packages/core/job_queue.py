from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from packages.core.logging_utils import log_structured
from packages.core.task_runs import add_event, finish_run, get_run, set_run_phase

JOB_STATES = {"queued", "running", "succeeded", "failed", "cancelled"}


@dataclass
class JobItem:
    job_id: str
    run_id: str
    request_id: str
    execute: Callable[[Callable[[], bool]], dict]
    state: str = "queued"
    cancel_requested: bool = False
    error: str = ""


class BackgroundJobQueue:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._jobs: dict[str, JobItem] = {}
        self._run_to_job: dict[str, str] = {}
        self._lock = threading.RLock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="codeyz-job-worker", daemon=True)
        self._worker.start()

    def shutdown(self) -> None:
        self._stop.set()
        self._queue.put("")
        self._worker.join(timeout=3.0)

    def enqueue(self, run_id: str, request_id: str, execute: Callable[[Callable[[], bool]], dict]) -> dict[str, str]:
        job_id = uuid4().hex
        item = JobItem(job_id=job_id, run_id=run_id, request_id=request_id, execute=execute)
        with self._lock:
            self._jobs[job_id] = item
            self._run_to_job[run_id] = job_id
        self._queue.put(job_id)
        add_event(run_id, "job_state", "Job queued", {"job_id": job_id, "state": "queued"})
        log_structured(
            self._logger,
            logging.INFO,
            "job_queued",
            component="job_queue",
            request_id=request_id,
            run_id=run_id,
            job_id=job_id,
            state="queued",
        )
        return {"job_id": job_id, "run_id": run_id, "state": "queued"}

    def cancel(self, run_id: str) -> dict[str, str]:
        with self._lock:
            job_id = self._run_to_job.get(run_id, "")
            if not job_id or job_id not in self._jobs:
                return {"ok": "false", "run_id": run_id, "state": "missing"}
            job = self._jobs[job_id]
            job.cancel_requested = True
            if job.state == "queued":
                job.state = "cancelled"
                add_event(run_id, "job_state", "Job cancelled", {"job_id": job_id, "state": "cancelled"})
                set_run_phase(run_id, "cancelled")
                finish_run(run_id, "cancelled", "Run cancelled before execution")
                log_structured(
                    self._logger,
                    logging.INFO,
                    "job_cancelled",
                    component="job_queue",
                    request_id=job.request_id,
                    run_id=run_id,
                    job_id=job_id,
                    state="cancelled",
                )
            return {"ok": "true", "run_id": run_id, "job_id": job_id, "state": job.state}

    def get_state(self, run_id: str) -> str:
        with self._lock:
            job_id = self._run_to_job.get(run_id, "")
            if not job_id:
                return "missing"
            job = self._jobs.get(job_id)
            if not job:
                return "missing"
            return job.state

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not job_id:
                continue
            with self._lock:
                job = self._jobs.get(job_id)
            if not job:
                continue
            if job.cancel_requested or job.state == "cancelled":
                continue
            job.state = "running"
            add_event(job.run_id, "job_state", "Job started", {"job_id": job.job_id, "state": "running"})
            log_structured(
                self._logger,
                logging.INFO,
                "job_started",
                component="job_queue",
                request_id=job.request_id,
                run_id=job.run_id,
                job_id=job.job_id,
                state="running",
            )
            try:
                job.execute(lambda: bool(job.cancel_requested))
                if job.cancel_requested:
                    job.state = "cancelled"
                    add_event(job.run_id, "job_state", "Job cancelled", {"job_id": job.job_id, "state": "cancelled"})
                    log_structured(
                        self._logger,
                        logging.INFO,
                        "job_cancelled",
                        component="job_queue",
                        request_id=job.request_id,
                        run_id=job.run_id,
                        job_id=job.job_id,
                        state="cancelled",
                    )
                else:
                    job.state = "succeeded"
                    add_event(job.run_id, "job_state", "Job completed", {"job_id": job.job_id, "state": "succeeded"})
                    log_structured(
                        self._logger,
                        logging.INFO,
                        "job_completed",
                        component="job_queue",
                        request_id=job.request_id,
                        run_id=job.run_id,
                        job_id=job.job_id,
                        state="succeeded",
                    )
            except Exception as exc:
                job.state = "failed"
                job.error = str(exc)
                add_event(job.run_id, "job_state", "Job failed", {"job_id": job.job_id, "state": "failed", "error": str(exc)})
                run = get_run(job.run_id)
                if run is not None and str(run.get("status", "")) == "running":
                    set_run_phase(job.run_id, "failed")
                    finish_run(job.run_id, "failed", f"Background job failed: {exc}")
                log_structured(
                    self._logger,
                    logging.ERROR,
                    "job_failed",
                    component="job_queue",
                    request_id=job.request_id,
                    run_id=job.run_id,
                    job_id=job.job_id,
                    state="failed",
                    error=str(exc),
                )


_JOB_QUEUE: BackgroundJobQueue | None = None


def get_job_queue() -> BackgroundJobQueue:
    global _JOB_QUEUE
    if _JOB_QUEUE is None:
        _JOB_QUEUE = BackgroundJobQueue()
    return _JOB_QUEUE


def shutdown_job_queue() -> None:
    global _JOB_QUEUE
    if _JOB_QUEUE is not None:
        _JOB_QUEUE.shutdown()
        _JOB_QUEUE = None
