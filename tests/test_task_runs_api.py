from fastapi.testclient import TestClient

from packages.core.task_runs import add_event, claim_approval_event, create_run, finish_run, mark_approval_event, set_run_phase
from packages.server.app import app


def test_task_runs_endpoint_returns_data(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task API", "gpt-5.4-mini", "Autonom")

    client = TestClient(app)
    res = client.get("/task/runs", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    assert any(item["run_id"] == run_id for item in res.json()["runs"])


def test_task_policy_endpoint_returns_effective_policy(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    client = TestClient(app)
    res = client.get("/task/policy/review", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["profile"] == "review"
    assert isinstance(payload.get("policy"), dict)
    assert "max_files_changed" in payload["policy"]


def test_task_run_detail_exposes_metrics(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task metrics api", "gpt-5.4-mini", "Autonom", profile="safe_mode")
    add_event(run_id, "diff", "d", {"file": "a.py", "added_lines": 1, "removed_lines": 1, "hunks_count": 1})
    finish_run(run_id, "done", "ok")

    client = TestClient(app)
    res = client.get(f"/task/runs/{run_id}", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["profile"] == "safe_mode"
    assert isinstance(payload.get("metrics"), dict)
    assert payload["metrics"]["files_changed_count"] >= 1


def test_task_run_detail_exposes_phase_for_running_run(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task phase api", "gpt-5.4-mini", "Autonom", profile="review")
    set_run_phase(run_id, "planning")
    add_event(run_id, "plan", "ready", {"estimated_input_tokens": 12})

    client = TestClient(app)
    res = client.get(f"/task/runs/{run_id}", headers={"x-api-key": "token123"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["phase"] == "planning"
    assert payload["metrics"]["current_phase"] == "planning"
    assert payload["metrics"]["duration_ms"] >= 0
    assert isinstance(payload.get("policy"), dict)


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


def test_approve_patch_rejects_non_approval_event(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    run_id = create_run("Task no approval", "gpt-5.4-mini", "Autonom")
    event = add_event(run_id, "error", "Patch failed", {"error": "x"})

    client = TestClient(app)
    res = client.post(f"/task/runs/{run_id}/approve-patch/{event['event_id']}", headers={"x-api-key": "token123"})
    assert res.status_code == 400
    payload = res.json()
    assert payload["code"] == "event_not_approvable"


def test_approve_patch_applies_exact_stored_patch_and_emits_event(monkeypatch, tmp_path) -> None:
    from packages.core.project_paths import add_project_path, get_current_project, set_current_project

    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    ws = tmp_path / "ws"
    ws.mkdir()
    old_project = get_current_project()
    add_project_path(str(ws))
    set_current_project(str(ws))
    try:
        target = ws / "a.txt"
        target.write_text("line1\nline2\nline3\n", encoding="utf-8")
        diff_text = "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2-approved\n line3"

        run_id = create_run("Task approval apply", "gpt-5.4-mini", "Autonom")
        event = add_event(
            run_id,
            "approval_required",
            "High-risk patch requires approval",
            {
                "file": "a.txt",
                "risk_level": "high",
                "reasons": ["high_deletion_ratio"],
                "stats": {"changed_lines": 40},
                "patch_preview": diff_text[:120],
                "patch": {"file_path": "a.txt", "unified_diff": diff_text},
            },
        )

        client = TestClient(app)
        res = client.post(
            f"/task/runs/{run_id}/approve-patch/{event['event_id']}",
            headers={"x-api-key": "token123"},
        )
        assert res.status_code == 200
        payload = res.json()
        assert payload["ok"] is True
        assert payload["event"]["event_type"] == "approval_applied"
        assert payload["event"]["data"]["source_event_id"] == event["event_id"]
        assert payload["event"]["data"]["file_status"] in {"added", "modified", "deleted", "unknown"}
        assert "added_lines" in payload["event"]["data"]
        assert "removed_lines" in payload["event"]["data"]
        assert payload["event"]["data"]["approval_required"] is False
        assert payload["result"]["rollback_id"]
        assert "line2-approved" in target.read_text(encoding="utf-8")
    finally:
        set_current_project(old_project)


def test_approve_patch_failure_emits_error_and_keeps_file(monkeypatch, tmp_path) -> None:
    from packages.core.project_paths import add_project_path, get_current_project, set_current_project

    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    ws = tmp_path / "ws"
    ws.mkdir()
    old_project = get_current_project()
    add_project_path(str(ws))
    set_current_project(str(ws))
    try:
        target = ws / "b.txt"
        original = "alpha\nbeta\ngamma\n"
        target.write_text(original, encoding="utf-8")
        bad_diff = "@@ -1,3 +1,3 @@\n alpha\n-WRONG\n+beta-updated\n gamma"

        run_id = create_run("Task approval fail", "gpt-5.4-mini", "Autonom")
        event = add_event(
            run_id,
            "approval_required",
            "High-risk patch requires approval",
            {
                "file": "b.txt",
                "risk_level": "high",
                "reasons": ["high_deletion_ratio"],
                "stats": {"changed_lines": 40},
                "patch_preview": bad_diff[:120],
                "patch": {"file_path": "b.txt", "unified_diff": bad_diff},
            },
        )

        client = TestClient(app)
        res = client.post(
            f"/task/runs/{run_id}/approve-patch/{event['event_id']}",
            headers={"x-api-key": "token123"},
        )
        assert res.status_code == 400
        assert target.read_text(encoding="utf-8") == original

        detail = client.get(f"/task/runs/{run_id}", headers={"x-api-key": "token123"})
        events = detail.json()["events"]
        assert any(e["event_type"] == "error" and e["title"] == "Approval apply failed" for e in events)
    finally:
        set_current_project(old_project)


def test_approve_patch_second_call_conflict_and_no_double_apply(monkeypatch, tmp_path) -> None:
    from packages.core.project_paths import add_project_path, get_current_project, set_current_project

    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    ws = tmp_path / "ws"
    ws.mkdir()
    old_project = get_current_project()
    add_project_path(str(ws))
    set_current_project(str(ws))
    try:
        target = ws / "c.txt"
        target.write_text("a\nb\n", encoding="utf-8")
        diff_text = "@@ -1,2 +1,2 @@\n a\n-b\n+b2"
        run_id = create_run("Task approval twice", "gpt-5.4-mini", "Autonom")
        event = add_event(
            run_id,
            "approval_required",
            "High-risk patch requires approval",
            {
                "file": "c.txt",
                "risk_level": "high",
                "reasons": ["high_deletion_ratio"],
                "stats": {"changed_lines": 40},
                "patch_preview": diff_text[:120],
                "patch": {"file_path": "c.txt", "unified_diff": diff_text},
            },
        )
        client = TestClient(app)
        first = client.post(
            f"/task/runs/{run_id}/approve-patch/{event['event_id']}",
            headers={"x-api-key": "token123"},
        )
        assert first.status_code == 200
        after_first = target.read_text(encoding="utf-8")
        second = client.post(
            f"/task/runs/{run_id}/approve-patch/{event['event_id']}",
            headers={"x-api-key": "token123"},
        )
        assert second.status_code == 409
        assert second.json()["code"] in {"approval_already_applied", "approval_already_claimed"}
        assert target.read_text(encoding="utf-8") == after_first
    finally:
        set_current_project(old_project)


def test_claim_approval_event_atomic_states() -> None:
    run_id = create_run("claim", "gpt-5.4-mini", "Autonom")
    source = "evt-1"
    assert claim_approval_event(run_id, source) is True
    assert claim_approval_event(run_id, source) is False
    mark_approval_event(run_id, source, "failed")
    assert claim_approval_event(run_id, source) is True
