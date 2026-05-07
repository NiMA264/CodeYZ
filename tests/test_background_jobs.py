from __future__ import annotations

import time

from fastapi.testclient import TestClient

from packages.core.job_queue import shutdown_job_queue
from packages.server import routes_task
from packages.server.app import app


def setup_function() -> None:
    shutdown_job_queue()


def teardown_function() -> None:
    shutdown_job_queue()


def test_task_auto_returns_quickly_with_run_id(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")

    def fake_run(*_args, **_kwargs):
        time.sleep(0.2)
        return {"ok": True}

    monkeypatch.setattr(routes_task, "run_autonomous_task", fake_run)
    client = TestClient(app)

    started = time.perf_counter()
    res = client.post(
        "/task/auto",
        headers={"x-api-key": "token123"},
        json={"task": "x", "access_level": "Autonom"},
    )
    elapsed = time.perf_counter() - started
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload.get("run_id")
    assert payload.get("job_id")
    assert payload.get("state") == "queued"
    assert elapsed < 0.15


def test_queued_job_can_be_cancelled(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    blocker = {"go": False}

    def fake_run(_task, **kwargs):
        should_cancel = kwargs.get("should_cancel")
        while not blocker["go"]:
            if should_cancel and should_cancel():
                return {"ok": False, "error": "cancelled"}
            time.sleep(0.01)
        return {"ok": True}

    monkeypatch.setattr(routes_task, "run_autonomous_task", fake_run)
    client = TestClient(app)

    res = client.post("/task/auto", headers={"x-api-key": "token123"}, json={"task": "x", "access_level": "Autonom"})
    run_id = res.json()["run_id"]
    cancel = client.post(f"/task/cancel/{run_id}", headers={"x-api-key": "token123"})
    assert cancel.status_code == 200
    assert cancel.json()["state"] in {"queued", "cancelled", "running"}


def test_running_job_cooperative_cancel(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")

    def fake_run(_task, **kwargs):
        should_cancel = kwargs.get("should_cancel")
        for _ in range(200):
            if should_cancel and should_cancel():
                return {"ok": False, "error": "cancelled"}
            time.sleep(0.005)
        return {"ok": True}

    monkeypatch.setattr(routes_task, "run_autonomous_task", fake_run)
    client = TestClient(app)
    res = client.post("/task/auto", headers={"x-api-key": "token123"}, json={"task": "x", "access_level": "Autonom"})
    run_id = res.json()["run_id"]
    time.sleep(0.05)
    cancel = client.post(f"/task/cancel/{run_id}", headers={"x-api-key": "token123"})
    assert cancel.status_code == 200
