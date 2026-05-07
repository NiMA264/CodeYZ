from pathlib import Path
from contextlib import asynccontextmanager

import logging
import os
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

from packages.core.agent import ask
from packages.core.automations_store import initialize_automations_storage
from packages.core.context_manager import (
    build_chat_context,
    list_pinned_files,
    pin_file,
    unpin_file,
)
from packages.core.context_policy import should_attach_code_context
from packages.core.indexer import build_index, index_status, search_files
from packages.core.logging_utils import log_structured
from packages.core.permissions import READ_ONLY
from packages.core.path_security import ensure_no_blocked_parts, ensure_within_root
from packages.core.plugins import list_plugins, load_plugins, register_plugin
from packages.core.project_paths import get_current_project
from packages.core.sessions import add_message, create_session
from packages.core.sessions import initialize_sessions_storage
from packages.core.task_runs import initialize_task_runs_storage
from packages.core.workspace_context import build_workspace_context
from packages.server.auth import require_auth
from packages.server.errors import error_payload, error_response, raise_api_error
from packages.server.routes_automation import router as automations_router
from packages.server.routes_plugins import router as plugins_router
from packages.server.routes_projects import router as projects_router
from packages.server.routes_rollback import router as rollback_router
from packages.server.routes_task import router as task_router
from packages.tools.git import git_diff, git_status

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_sessions_storage()
    initialize_automations_storage()
    initialize_task_runs_storage()
    yield


app = FastAPI(title="CodeYZ Local Server", version="0.3.0", lifespan=lifespan)
STATIC_DIR = Path(__file__).resolve().parent / "static"
PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins"
VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_DIRS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
ALLOWED_MODELS = {"gpt-5.4-mini", "gpt-5.4", "gpt-5.5"}
ALLOWED_MODES = {"Chat", "Code", "Review", "Fix", "Projekt planen"}
ALLOWED_ACCESS = {"Nur lesen", "Dateien ändern", "Tests ausführen", "Autonom", "Gefährlich deaktiviert"}

app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
logger = logging.getLogger(__name__)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "") or uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[override]
    request_id = str(getattr(request.state, "request_id", ""))
    detail = exc.detail
    if isinstance(detail, dict) and {"ok", "code", "message", "hint"}.issubset(detail.keys()):
        payload = dict(detail)
        if request_id and "request_id" not in payload:
            payload["request_id"] = request_id
    else:
        payload = error_payload(
            code=f"http_{exc.status_code}",
            message=str(detail) if detail else "Request failed",
            hint="Check request parameters or permissions.",
            request_id=request_id,
        )

    log_structured(
        logger,
        logging.WARNING,
        "http_exception",
        component="api",
        request_id=request_id,
        code=str(payload.get("code", "")),
        status_code=exc.status_code,
    )

    return error_response(
        status_code=exc.status_code,
        code=str(payload.get("code", f"http_{exc.status_code}")),
        message=str(payload.get("message", "Request failed")),
        hint=str(payload.get("hint", "")),
        request_id=request_id,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):  # type: ignore[override]
    request_id = str(getattr(request.state, "request_id", ""))
    log_structured(
        logger,
        logging.WARNING,
        "request_validation_error",
        component="api",
        request_id=request_id,
        errors_count=len(exc.errors()),
    )
    return error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        hint=str(exc.errors()[:2]),
        request_id=request_id,
    )


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: str = ""
    selected_file: str | None = None
    model: str | None = None
    mode: str | None = None
    access_level: str | None = None
    plan_mode: bool | None = None
    attachments_metadata: list[dict] | None = None


class PinnedFileRequest(BaseModel):
    path: str


def _ping_handler(input_data: dict | None = None) -> dict[str, str]:
    _ = input_data
    return {"status": "ok"}


def _resolve_file_in_current_project(rel_path: str) -> Path:
    root = Path(get_current_project()).resolve()
    target = ensure_within_root(root / rel_path, root)
    if target.name in BLOCKED_NAMES:
        raise ValueError("Blocked file")
    ensure_no_blocked_parts(target, BLOCKED_DIRS)
    if not target.exists() or not target.is_file():
        raise ValueError("File not found")
    return target


def _validate_chat_options(payload: ChatRequest) -> None:
    if payload.model and payload.model not in ALLOWED_MODELS:
        raise_api_error(400, "unsupported_model", "Unsupported model", "Use one of: gpt-5.4-mini, gpt-5.4, gpt-5.5.")
    if payload.mode and payload.mode not in ALLOWED_MODES:
        raise_api_error(400, "unsupported_mode", "Unsupported mode", "Use a supported composer mode.")
    if payload.access_level and payload.access_level not in ALLOWED_ACCESS:
        raise_api_error(400, "unsupported_access_level", "Unsupported access level", "Use one of the configured access levels.")


def _access_rules_hint(access_level: str | None) -> str:
    if access_level == "Nur lesen":
        return "Access rules: explain and plan only. Never modify files or run commands."
    if access_level == "Dateien ändern":
        return "Access rules: suggest patches only, do not apply automatically."
    if access_level == "Tests ausführen":
        return "Access rules: test/build commands are allowed when needed."
    if access_level == "Autonom":
        return "Access rules: autonomous loop may be recommended via /task/auto."
    return "Access rules: never suggest destructive commands."


register_plugin(
    {
        "name": "ping",
        "description": "Simple health plugin",
        "version": "1.0",
        "permissions": ["read_files"],
        "functions": ["run"],
        "entry": "builtin",
        "enabled": True,
        "handler": _ping_handler,
    }
)
load_plugins(PLUGIN_DIR)
try:
    build_index(get_current_project())
except Exception:
    pass

app.include_router(projects_router, dependencies=[Depends(require_auth)])
app.include_router(plugins_router, dependencies=[Depends(require_auth)])
app.include_router(automations_router, dependencies=[Depends(require_auth)])
app.include_router(task_router, dependencies=[Depends(require_auth)])
app.include_router(rollback_router, dependencies=[Depends(require_auth)])


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/ui/")


@app.get("/ui")
def ui_root_no_slash() -> RedirectResponse:
    return RedirectResponse("/ui/")


@app.get("/ui/")
def ui_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    openai_status = "failed"
    if os.getenv("OPENAI_API_KEY"):
        try:
            _ = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            openai_status = "ok"
        except Exception:
            openai_status = "failed"

    index = index_status()
    index_flag = "built" if int(index.get("files_indexed", 0)) > 0 else "missing"
    version = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "unknown"
    return {
        "status": "ok",
        "openai": openai_status,
        "index": index_flag,
        "plugins": len(list_plugins()),
        "workspace": get_current_project(),
        "version": version,
    }


@app.get("/workspace/summary", dependencies=[Depends(require_auth)])
def workspace_summary() -> dict[str, str]:
    return {"summary": build_workspace_context()}


@app.get("/index/build", dependencies=[Depends(require_auth)])
def index_build_route() -> dict:
    data = build_index(get_current_project())
    return {"status": "ok", "files_indexed": len(data.get("items", []))}


@app.get("/index/status", dependencies=[Depends(require_auth)])
def index_status_route() -> dict:
    return index_status()


@app.get("/index/search", dependencies=[Depends(require_auth)])
def index_search_route(q: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20)) -> dict:
    return {"results": search_files(q, top_k=top_k)}


@app.get("/context/pinned", dependencies=[Depends(require_auth)])
def get_pinned_context() -> dict[str, list[str]]:
    return {"pinned_files": list_pinned_files()}


@app.post("/context/pinned", dependencies=[Depends(require_auth)])
def add_pinned_context(payload: PinnedFileRequest) -> dict[str, list[str]]:
    try:
        pin_file(payload.path)
    except ValueError as exc:
        raise_api_error(400, "invalid_pinned_file", str(exc), "Pin only files inside the current workspace.")
    return {"pinned_files": list_pinned_files()}


@app.delete("/context/pinned", dependencies=[Depends(require_auth)])
def remove_pinned_context(path: str = Query(..., min_length=1)) -> dict[str, list[str]]:
    unpin_file(path)
    return {"pinned_files": list_pinned_files()}


@app.get("/files/read", dependencies=[Depends(require_auth)])
def read_file_preview(path: str = Query(..., min_length=1)) -> dict[str, str]:
    try:
        target = _resolve_file_in_current_project(path)
        content = target.read_text(encoding="utf-8")
    except ValueError as exc:
        raise_api_error(400, "invalid_file_path", str(exc), "Use a relative path inside the current workspace.")
    except Exception as exc:
        raise_api_error(400, "file_read_failed", f"Could not read file: {exc}", "Check file encoding and permissions.")

    if len(content) > 12000:
        content = content[:12000] + "\n\n[TRUNCATED]"

    return {"path": path, "content": content}


@app.post("/chat", dependencies=[Depends(require_auth)])
def chat(payload: ChatRequest) -> dict[str, str]:
    _validate_chat_options(payload)

    session_id = payload.session_id or create_session()
    add_message(session_id, "user", payload.message)

    access_level = payload.access_level or READ_ONLY
    force_plan_mode = bool(payload.plan_mode) or access_level == READ_ONLY

    full_context = payload.context or ""
    pinned = list_pinned_files()
    attach_code_context = should_attach_code_context(
        payload.message,
        payload.mode,
        selected_file=payload.selected_file,
        pinned_count=len(pinned),
    )

    if attach_code_context:
        try:
            pin_context = build_chat_context(
                payload.selected_file,
                pinned,
                query=payload.message,
                max_chars=12000,
            )
            if pin_context:
                full_context = f"{full_context}\n\nPinned/selected context:\n{pin_context}".strip()
        except ValueError as exc:
            raise_api_error(400, "context_build_failed", str(exc), "Check selected/pinned files for workspace boundaries.")

    if payload.attachments_metadata:
        full_context = f"{full_context}\n\nAttachments metadata:\n{payload.attachments_metadata}".strip()

    full_context = f"{full_context}\n\n{_access_rules_hint(access_level)}".strip()

    if attach_code_context:
        workspace_context = build_workspace_context()
        full_context = f"{full_context}\n\nWorkspace context:\n{workspace_context}".strip()

    answer = ask(
        payload.message,
        full_context,
        model=payload.model,
        mode=payload.mode,
        access_level=access_level,
        plan_mode=force_plan_mode,
    )

    add_message(session_id, "assistant", answer)
    return {"session_id": session_id, "response": answer}


@app.get("/git/status", dependencies=[Depends(require_auth)])
def git_status_route() -> dict[str, str]:
    return {"status": git_status()}


@app.get("/git/diff", dependencies=[Depends(require_auth)])
def git_diff_route() -> dict[str, str]:
    return {"diff": git_diff()}



