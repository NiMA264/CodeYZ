from fastapi.testclient import TestClient

from packages.core.task_runs import add_event, create_run
from packages.server.app import app


def test_task_runs_endpoint_returns_data(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task API", "gpt-5.4-mini", "Autonom")

    client = TestClient(app)
    res = client.get("/task/runs", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    assert any(item["run_id"] == run_id for item in res.json()["runs"])


def test_task_run_detail_preserves_approval_required_event(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task approval", "gpt-5.4-mini", "Autonom")
    add_event(
        run_id,
        "approval_required",
        "High-risk patch requires approval",
        {
            "file": "a.py",
            "risk_level": "high",
            "reasons": ["high_deletion_ratio"],
            "stats": {"changed_lines": 40},
            "patch_preview": "@@ -1,2 +1,0 @@ ...",
        },
    )

    client = TestClient(app)
    res = client.get(f"/task/runs/{run_id}", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    events = res.json()["events"]
    approval = next(e for e in events if e["event_type"] == "approval_required")
    assert approval["title"] == "High-risk patch requires approval"
    assert approval["data"]["risk_level"] == "high"
