from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from packages.core.plugins import (
    call_plugin,
    disable_plugin,
    enable_plugin,
    list_plugins,
    load_plugins,
)
from packages.server.errors import raise_api_error

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
    try:
        load_plugins(PLUGIN_ROOT)
    except ValueError as exc:
        raise_api_error(400, "plugin_config_invalid", str(exc), "Fix trusted plugin hash config JSON and retry.")
    return {"plugins": list_plugins()}


@router.post("/enable")
def enable_plugin_route(payload: PluginNameRequest) -> dict[str, str]:
    try:
        enable_plugin(payload.name)
    except ValueError as exc:
        raise_api_error(404, "plugin_not_found", str(exc), "Check the plugin name via GET /plugins.")
    return {"status": "enabled", "name": payload.name}


@router.post("/disable")
def disable_plugin_route(payload: PluginNameRequest) -> dict[str, str]:
    try:
        disable_plugin(payload.name)
    except ValueError as exc:
        raise_api_error(404, "plugin_not_found", str(exc), "Check the plugin name via GET /plugins.")
    return {"status": "disabled", "name": payload.name}


@router.post("/run")
def run_plugin_route(payload: PluginRunRequest) -> dict:
    try:
        result = call_plugin(payload.name, payload.input_data, access_level=payload.access_level)
    except ValueError as exc:
        raise_api_error(404, "plugin_not_found", str(exc), "Check the plugin name via GET /plugins.")
    except PermissionError as exc:
        raise_api_error(403, "plugin_permission_denied", str(exc), "Increase access level if this action is intended.")
    except Exception as exc:
        raise_api_error(400, "plugin_execution_failed", f"Plugin execution failed: {exc}", "Inspect plugin input and permissions.")
    return {"plugin": payload.name, "result": result}
