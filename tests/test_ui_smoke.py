from __future__ import annotations

import importlib.util
import socket
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packages.server.app import app


def _is_missing_playwright_browser(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = (
        "executable doesn't exist",
        "please run the following command to download new browsers",
        "playwright install",
        "browser binaries",
        "chrome-headless-shell",
    )
    return any(marker in message for marker in markers)


def test_ui_route_and_module_wiring() -> None:
    client = TestClient(app)
    response = client.get("/ui/")
    assert response.status_code == 200
    html = response.text

    assert '<script type="module" src="/ui/app.js"></script>' in html
    assert 'id="chat-form"' in html
    assert 'id="messages"' in html
    assert 'id="explorer"' in html
    assert 'id="runs-list"' in html
    assert 'id="plugins-list"' in html
    assert 'id="settings-panel"' in html
    assert 'id="diff-files-list"' in html
    assert 'id="profile-select"' in html
    assert 'id="profile-state"' in html
    assert 'id="run-metrics-summary"' in html


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright is not installed; run with `pip install -e .[dev]`",
)
def test_ui_initializes_without_browser_errors() -> None:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen(
        [
            "py",
            "-3.11",
            "-m",
            "uvicorn",
            "packages.server.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        deadline = time.time() + 12
        ready = False
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    ready = True
                    break
            except OSError:
                time.sleep(0.2)
        assert ready, "uvicorn test server did not start in time"

        page_errors: list[str] = []
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except PlaywrightError as exc:
                if _is_missing_playwright_browser(exc):
                    pytest.skip(
                        "playwright browser binaries are not installed; "
                        "run `playwright install` to enable UI smoke test"
                    )
                raise
            page = browser.new_page()
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.goto(f"http://127.0.0.1:{port}/ui/", wait_until="domcontentloaded")
            page.wait_for_selector("#chat-form")
            page.wait_for_selector("#messages")
            page.wait_for_selector("#explorer")
            page.wait_for_selector("#runs-list")
            page.wait_for_selector("#plugins-list")
            page.wait_for_selector("#settings-panel")
            page.wait_for_selector("#diff-files-list")
            page.wait_for_selector("#profile-select")
            page.wait_for_selector("#profile-state")
            page.wait_for_selector("#run-metrics-summary")
            browser.close()

        assert not page_errors, f"browser page errors: {page_errors}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
