from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.core.plugins import (
    call_plugin,
    disable_plugin,
    enable_plugin,
    list_plugins,
    load_plugins,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])
PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "plugins"


class PluginNameRequest(BaseModel):
    name: str


class PluginRunRequest(BaseModel):
    name: str
    input_data: dict | None = None
    access_level: str | None = None


@router.get("")
def get_plugins() -> dict[str, list[dict]]:
    load_plugins(PLUGIN_ROOT)
    return {"plugins": list_plugins()}


@router.post("/enable")
def enable_plugin_route(payload: PluginNameRequest) -> dict[str, str]:
    try:
        enable_plugin(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "enabled", "name": payload.name}


@router.post("/disable")
def disable_plugin_route(payload: PluginNameRequest) -> dict[str, str]:
    try:
        disable_plugin(payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "disabled", "name": payload.name}


@router.post("/run")
def run_plugin_route(payload: PluginRunRequest) -> dict:
    try:
        result = call_plugin(payload.name, payload.input_data, access_level=payload.access_level)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Plugin execution failed: {exc}") from exc
    return {"plugin": payload.name, "result": result}
