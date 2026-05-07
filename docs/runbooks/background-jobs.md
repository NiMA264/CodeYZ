# Background Jobs Runbook

## Purpose

CodeYZ runs autonomous tasks (`/task/auto`) through a local background worker queue so API requests return quickly with a `run_id`.

## Lifecycle

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Lifecycle transitions are recorded as `job_state` events inside the existing task run timeline.

## APIs

- Start job: `POST /task/auto`
  - returns `run_id`, `job_id`, and initial `state=queued`
- Observe runs: `GET /task/runs`, `GET /task/runs/{run_id}`
- Cancel run: `POST /task/cancel/{run_id}`

## Cancellation behavior

- Queued job: cancelled before execution.
- Running job: cooperative cancellation via periodic checks in autonomous loop.

## Logging / Observability

Structured logs include:

- `component=job_queue`
- `request_id`
- `run_id`
- `job_id`
- event names: `job_queued`, `job_started`, `job_completed`, `job_failed`, `job_cancelled`

## Shutdown

The queue worker is shut down on FastAPI lifespan shutdown (`shutdown_job_queue()`).
