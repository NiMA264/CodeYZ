from fastapi.testclient import TestClient

from packages.core.task_runs import create_run
from packages.server.app import app


def test_task_runs_endpoint_returns_data(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task API", "gpt-5.4-mini", "Autonom")

    client = TestClient(app)
    res = client.get("/task/runs", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    assert any(item["run_id"] == run_id for item in res.json()["runs"])
