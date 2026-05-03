import typer
import uvicorn
from rich.console import Console

from packages.core.agent import ask
from packages.core.loop import run_task
from packages.tools.git import git_diff, git_status
from packages.tools.shell import run_shell

app = typer.Typer(help="CodeYZ local coding agent")
console = Console()


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
def server():
    """Start local CodeYZ FastAPI server."""
    uvicorn.run("packages.server.app:app", host="127.0.0.1", port=8765)


if __name__ == "__main__":
    app()
