from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.core.file_tree import build_file_tree
from packages.core.project_paths import (
    add_project_path,
    ensure_allowed_path,
    get_current_project,
    list_project_paths,
    set_current_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    path: str


@router.get("")
def get_projects() -> dict[str, list[str]]:
    return {"projects": list_project_paths()}


@router.post("")
def create_project(payload: ProjectCreateRequest) -> dict[str, str]:
    try:
        added = add_project_path(payload.path)
        return {"added": added}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/current")
def get_current_project_route() -> dict[str, str]:
    return {"current": get_current_project()}


@router.post("/current")
def set_current_project_route(payload: ProjectCreateRequest) -> dict[str, str]:
    try:
        current = set_current_project(payload.path)
        return {"current": current}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tree")
def get_project_tree() -> dict:
    current = get_current_project()
    try:
        allowed_root = ensure_allowed_path(current)
        return build_file_tree(str(allowed_root))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
