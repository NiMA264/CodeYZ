from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    entry = root / "packages" / "cli" / "main.py"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "codeyz",
        "--add-data",
        f"{root / 'VERSION'};.",
        "--add-data",
        f"{root / 'packages' / 'server' / 'static'};packages/server/static",
        "--hidden-import",
        "fastapi",
        "--hidden-import",
        "uvicorn",
        "--hidden-import",
        "typer",
        "--hidden-import",
        "rich",
        "--hidden-import",
        "packages.server.app",
        "--hidden-import",
        "packages.server.routes_plugins",
        "--hidden-import",
        "packages.server.routes_projects",
        "--hidden-import",
        "packages.server.routes_task",
        "--hidden-import",
        "packages.server.routes_rollback",
        "--hidden-import",
        "packages.core.plugins.plugin_loader",
        "--hidden-import",
        "packages.core.plugins.plugin_registry",
        "--hidden-import",
        "packages.core.plugins.plugin_permissions",
        str(entry),
    ]
    print("Running:", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=root, check=False)
    if completed.returncode != 0:
        return completed.returncode
    exe = root / "dist" / "codeyz.exe"
    if exe.exists():
        print(f"Build successful: {exe}")
        return 0
    print("Build failed: dist/codeyz.exe not found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
