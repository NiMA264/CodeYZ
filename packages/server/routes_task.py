from fastapi import APIRouter, status
from pydantic import BaseModel

from packages.core.agent_loop import run_autonomous_task
from packages.core.loop import run_task
from packages.core.model_router import set_role_models
from packages.core.permissions import can_run_autonomous
from packages.core.task_runs import get_run, list_runs
from packages.server.errors import raise_api_error

router = APIRouter(prefix="/task", tags=["task"])


class TaskRequest(BaseModel):
    task: str
    model: str | None = None
    access_level: str | None = None
    multi_agent: bool | None = None
    max_cost_usd: float | None = None
    role_models: dict[str, str] | None = None


@router.post("")
def task(payload: TaskRequest) -> dict[str, str]:
    return {"result": run_task(payload.task)}


@router.post("/auto")
def task_auto(payload: TaskRequest) -> dict:
    if payload.role_models:
        try:
            set_role_models(payload.role_models)
        except ValueError as exc:
            raise_api_error(400, "invalid_role_models", str(exc), "Use only allowed model names per role.")

    if not can_run_autonomous(payload.access_level):
        raise_api_error(
            status.HTTP_403_FORBIDDEN,
            "autonomous_access_denied",
            "Access denied: /task/auto requires access level 'Autonom'",
            "Set access level to 'Autonom' in Composer or request payload.",
        )
    return run_autonomous_task(
        payload.task,
        model=payload.model,
        access_level=payload.access_level,
        use_multi_agent=bool(payload.multi_agent),
        max_cost_usd=payload.max_cost_usd,
    )


@router.get("/runs")
def task_runs() -> dict:
    return {"runs": list_runs()}


@router.get("/runs/{run_id}")
def task_run_by_id(run_id: str) -> dict:
    run = get_run(run_id)
    if run is None:
        raise_api_error(404, "run_not_found", "Run not found", "List runs via GET /task/runs first.")
    return run
