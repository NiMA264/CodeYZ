import logging
import os
import socket
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
        console.print(
            "Kein API-Key gesetzt. Lösung: OPENAI_API_KEY setzen oder später in %APPDATA%\\CodeYZ\\.env eintragen.",
            style="yellow",
        )
        return
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    os.environ["OPENAI_API_KEY"] = key
    console.print(f"API-Key gespeichert in {env_file}", style="green")


def _format_expected_error(exc: Exception) -> str:
    text = str(exc)
    if "plugin_config_invalid" in text or "Plugin trust config invalid" in text:
        return (
            "Plugin-Trust-Konfiguration ist ungültig. "
            "Lösung: trusted_plugins.json auf gültiges JSON-Objekt prüfen."
        )
    return text


def _is_port_available(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


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
    try:
        status_text = git_status()
        if status_text.strip():
            console.print(status_text, markup=False)
        else:
            console.print("Kein Git-Status verfügbar.", style="yellow")
    except Exception as exc:
        console.print(f"Status fehlgeschlagen: {_format_expected_error(exc)}", style="red")


@app.command()
def diff():
    """Show git diff."""
    try:
        diff_text = git_diff()
        if diff_text.strip():
            console.print(diff_text, markup=False)
        else:
            console.print("Keine Änderungen.", style="green")
    except Exception as exc:
        console.print(f"Diff fehlgeschlagen: {_format_expected_error(exc)}", style="red")


@app.command()
def test():
    """Run detected basic tests."""
    try:
        console.print("Starte Tests: pytest", style="cyan")
        console.print(run_shell("py -3.11 -m pytest"), markup=False)
    except Exception as exc:
        console.print(f"Tests fehlgeschlagen: {_format_expected_error(exc)}", style="red")


@app.command()
def server(
    open_browser: bool = typer.Option(False, "--open-browser", help="Open UI in browser"),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Server port"),
):
    """Start local CodeYZ FastAPI server."""
    from packages.server.app import app as fastapi_app

    if not os.getenv("OPENAI_API_KEY") and not get_env_file_path().exists():
        console.print("OPENAI_API_KEY fehlt.", style="red")
        console.print("Fix: setx OPENAI_API_KEY \"sk-...\" und neues Terminal öffnen.", style="yellow")
        console.print("Alternativ: %APPDATA%\\CodeYZ\\.env mit OPENAI_API_KEY=... anlegen.", style="yellow")
        return

    try:
        runtime_dirs = ensure_runtime_dirs()
    except Exception as exc:
        console.print(f"Runtime root nicht schreibbar: {exc}", style="red")
        console.print("Fix: CODEYZ_RUNTIME_ROOT auf beschreibbaren Pfad setzen.", style="yellow")
        return

    if not _is_port_available(port):
        console.print(f"Port {port} ist bereits belegt.", style="red")
        console.print("Fix: Prozess beenden oder anderen Port verwenden (z. B. --port 8766).", style="yellow")
        return

    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}/ui/")
    console.print(f"Server startet auf http://127.0.0.1:{port}/ui/", style="green")
    console.print(f"Runtime root: {runtime_dirs['root']}", style="cyan")

    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=port)
    except OSError as exc:
        if "10048" in str(exc) or "address already in use" in str(exc).lower():
            console.print(f"Port {port} ist bereits belegt.", style="red")
            console.print("Fix: Prozess beenden oder --port <port> verwenden.", style="yellow")
            return
        console.print(f"Serverstart fehlgeschlagen: {exc}", style="red")


@app.command("chat")
def chat_cmd(message: str):
    """Ask CodeYZ via short chat alias."""
    console.print(ask(message), markup=False)


@app.command("task")
def task_cmd(task_text: str):
    """Run autonomous-safe task analysis alias."""
    try:
        console.print("Task wird ausgeführt...", style="cyan")
        console.print(run_task(task_text), markup=False)
    except Exception as exc:
        console.print(f"Task fehlgeschlagen: {_format_expected_error(exc)}", style="red")


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
            style = "white"
            if line.startswith(("✔", "[OK]")):
                style = "green"
            elif line.startswith(("⚠", "[WARN]")):
                style = "yellow"
            elif line.startswith(("✖", "[FAIL]")):
                style = "red"
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
