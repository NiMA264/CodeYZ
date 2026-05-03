from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from packages.core.agent import ask
from packages.core.plugins import register_plugin
from packages.core.sessions import add_message, create_session
from packages.server.auth import require_auth
from packages.server.routes_automation import router as automations_router
from packages.server.routes_plugins import router as plugins_router
from packages.server.routes_projects import router as projects_router
from packages.server.routes_task import router as task_router
from packages.tools.git import git_diff, git_status

app = FastAPI(title="CodeYZ Local Server", version="0.3.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"

app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: str = ""


def _ping_handler() -> dict[str, str]:
    return {"status": "ok"}


register_plugin("ping", "Simple health plugin", _ping_handler)

app.include_router(projects_router, dependencies=[Depends(require_auth)])
app.include_router(plugins_router, dependencies=[Depends(require_auth)])
app.include_router(automations_router, dependencies=[Depends(require_auth)])
app.include_router(task_router, dependencies=[Depends(require_auth)])


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
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", dependencies=[Depends(require_auth)])
def chat(payload: ChatRequest) -> dict[str, str]:
    session_id = payload.session_id or create_session()
    add_message(session_id, "user", payload.message)

    answer = ask(payload.message, payload.context)

    add_message(session_id, "assistant", answer)
    return {"session_id": session_id, "response": answer}


@app.get("/git/status", dependencies=[Depends(require_auth)])
def git_status_route() -> dict[str, str]:
    return {"status": git_status()}


@app.get("/git/diff", dependencies=[Depends(require_auth)])
def git_diff_route() -> dict[str, str]:
    return {"diff": git_diff()}
