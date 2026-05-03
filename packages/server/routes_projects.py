from fastapi import APIRouter
from pydantic import BaseModel

from packages.core.project_paths import add_allowed_path, list_allowed_paths

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    path: str


@router.get("")
def get_projects() -> dict[str, list[str]]:
    return {"projects": list_allowed_paths()}


@router.post("")
def create_project(payload: ProjectCreateRequest) -> dict[str, str]:
    added = add_allowed_path(payload.path)
    return {"added": added}
