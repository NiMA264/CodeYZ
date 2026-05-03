from fastapi import APIRouter
from pydantic import BaseModel

from packages.core.agent_loop import run_autonomous_task
from packages.core.loop import run_task

router = APIRouter(prefix="/task", tags=["task"])


class TaskRequest(BaseModel):
    task: str


@router.post("")
def task(payload: TaskRequest) -> dict[str, str]:
    return {"result": run_task(payload.task)}


@router.post("/auto")
def task_auto(payload: TaskRequest) -> dict:
    return run_autonomous_task(payload.task)
