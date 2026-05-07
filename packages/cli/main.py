import logging
import os
import webbrowser

import typer
import uvicorn
from rich.console import Console

from packages.cli.setup import check_dependencies, check_environment, check_git
from packages.core.agent import ask
from packages.core.loop import run_task
from packages.core.logging_utils import JsonFormatter
from packages.core.runtime_paths import ensure_runtime_dirs, get_env_file_path
from scripts.release_zip import build_release_zip
from packages.tools.git import git_diff, git_status
from packages.tools.shell import run_shell

app = typer.Typer(help="CodeYZ local coding agent")
console = Console()


def _setup_logging() -> None:
    dirs = ensure_runtime_dirs()
    log_file = dirs["logs"] / "codeyz.log"
    handler = logging.FileHandler(str(log_file), encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)


def _ensure_first_run_env() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    env_file = get_env_file_path()
    if env_file.exists():
        return

    key = typer.prompt("Bitte OpenAI API Key eingeben", default="", show_default=False).strip()
    if not key:
        console.print("Kein API-Key gesetzt. Lösung: OPENAI_API_KEY setzen oder später in %APPDATA%\\CodeYZ\\.env eintragen.", style="yellow")
        return
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    os.environ["OPENAI_API_KEY"] = key
    console.print(f"API-Key gespeichert in {env_file}", style="green")


@app.callback()
def _bootstrap() -> None:
    _setup_logging()
    _ensure_first_run_env()


@app.command()
def ask_cmd(task: str):
    """Ask CodeYZ a simple question."""
    console.print(ask(task), markup=False)


@app.command("run-task-cmd")
def run_task_cmd(task: str):
    """Run the Phase 2 agent loop."""
    console.print(run_task(task), markup=False)


@app.command()
def status():
    """Show git status."""
    console.print(git_status(), markup=False)


@app.command()
def diff():
    """Show git diff."""
    console.print(git_diff(), markup=False)


@app.command()
def test():
    """Run detected basic tests."""
    try:
        console.print(run_shell("py -3.11 -m pytest"), markup=False)
    except Exception as exc:
        console.print(f"Test failed: {exc}", style="red")


@app.command()
def server(open_browser: bool = typer.Option(False, "--open-browser", help="Open UI in browser")):
    """Start local CodeYZ FastAPI server."""
    from packages.server.app import app as fastapi_app

    if open_browser:
        webbrowser.open("http://127.0.0.1:8765/ui/")
    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8765)
    except OSError as exc:
        if "10048" in str(exc) or "address already in use" in str(exc).lower():
            console.print("Port 8765 ist bereits belegt. Lösung: laufenden Prozess beenden oder anderen Port konfigurieren.", style="red")
            return
        raise


@app.command("chat")
def chat_cmd(message: str):
    """Ask CodeYZ via short chat alias."""
    console.print(ask(message), markup=False)


@app.command("task")
def task_cmd(task_text: str):
    """Run autonomous-safe task analysis alias."""
    console.print(run_task(task_text), markup=False)


@app.command("setup")
def setup_cmd():
    """Run local setup checks."""
    sections = [
        ("Environment", check_environment()),
        ("Dependencies", check_dependencies()),
        ("Git", check_git()),
    ]
    for title, lines in sections:
        console.print(f"\n{title}")
        for line in lines:
            style = "green" if line.startswith("✔") else "red"
            console.print(line, style=style)


@app.command("release-zip")
def release_zip_cmd():
    """Build Windows release ZIP package."""
    try:
        zip_path, size_bytes = build_release_zip()
        console.print(f"Release ZIP erstellt: {zip_path}", style="green")
        console.print(f"Dateigröße: {size_bytes} bytes")
    except Exception as exc:
        console.print(f"Release ZIP fehlgeschlagen: {exc}", style="red")


if __name__ == "__main__":
    app()


