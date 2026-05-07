from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BANNED_DIRS = ("node_modules/", "dist/", "build/")
MAX_ZIP_BYTES = 5 * 1024 * 1024


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, shell=False)
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, out.strip()


def check_artifact_hygiene() -> list[str]:
    errors: list[str] = []
    rc, out = _run(["git", "ls-files"])
    if rc != 0:
        return [f"git ls-files failed: {out}"]
    tracked = [line.strip() for line in out.splitlines() if line.strip()]
    tracked_existing = [p for p in tracked if (ROOT / p).exists()]
    banned = [p for p in tracked_existing if p.startswith(BANNED_DIRS)]
    if banned:
        errors.append(f"Banned tracked artifacts: {', '.join(banned[:10])}")
    zips = [p for p in tracked_existing if p.lower().endswith(".zip")]
    large_zips: list[str] = []
    for p in zips:
        rc_size, size_out = _run(["git", "cat-file", "-s", f"HEAD:{p}"])
        if rc_size != 0:
            continue
        try:
            size = int(size_out.strip())
        except ValueError:
            continue
        if size > MAX_ZIP_BYTES:
            large_zips.append(f"{p} ({size} bytes)")
    if large_zips:
        errors.append(f"Large tracked zip artifacts: {', '.join(large_zips[:10])}")
    return errors


def check_readme_install_instructions() -> list[str]:
    errors: list[str] = []
    readme = (ROOT / "README.md")
    if not readme.exists():
        return ["README.md missing"]
    text = readme.read_text(encoding="utf-8")
    required = [
        "python -m venv .venv",
        "pip install -e .",
        "codeyz setup",
        "codeyz server",
    ]
    for token in required:
        if token not in text:
            errors.append(f"README install instructions missing '{token}'")
    return errors


def run_release_check() -> int:
    errors: list[str] = []

    for path in ["VERSION", "docs/security.md", "docs/architecture.md"]:
        if not (ROOT / path).exists():
            errors.append(f"Missing required file: {path}")

    errors.extend(check_readme_install_instructions())
    errors.extend(check_artifact_hygiene())

    rc, out = _run([sys.executable, "-m", "ruff", "check", "."])
    if rc != 0:
        errors.append(f"ruff check failed:\n{out}")

    rc, out = _run([sys.executable, "-m", "pytest", "-q"])
    if rc != 0:
        errors.append(f"pytest failed:\n{out}")

    if errors:
        print("RELEASE CHECK FAILED")
        for err in errors:
            print(f"- {err}")
        return 1

    print("RELEASE CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_release_check())
