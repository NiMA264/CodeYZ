from threading import Lock
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/automations", tags=["automations"])

_AUTOMATIONS: list[dict[str, str]] = []
_LOCK = Lock()


class AutomationCreateRequest(BaseModel):
    name: str
    prompt: str
    schedule: str


@router.get("")
def get_automations() -> dict[str, list[dict[str, str]]]:
    with _LOCK:
        return {"automations": list(_AUTOMATIONS)}


@router.post("")
def create_automation(payload: AutomationCreateRequest) -> dict[str, str]:
    item = {
        "id": uuid4().hex,
        "name": payload.name,
        "prompt": payload.prompt,
        "schedule": payload.schedule,
    }
    with _LOCK:
        _AUTOMATIONS.append(item)
    return item
