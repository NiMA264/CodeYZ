from fastapi import APIRouter
from pydantic import BaseModel

from packages.core.automations_store import create_automation, list_automations

router = APIRouter(prefix="/automations", tags=["automations"])


class AutomationCreateRequest(BaseModel):
    name: str
    prompt: str
    schedule: str


@router.get("")
def get_automations() -> dict[str, list[dict[str, str]]]:
    return {"automations": list_automations()}


@router.post("")
def create_automation_route(payload: AutomationCreateRequest) -> dict[str, str]:
    return create_automation(
        name=payload.name,
        prompt=payload.prompt,
        schedule=payload.schedule,
    )
