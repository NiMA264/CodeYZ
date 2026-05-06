from packages.core.task_runs import add_event, create_run, finish_run, get_run, list_runs, set_run_phase


def test_create_list_get_run() -> None:
    run_id = create_run("Task A", "gpt-5.4-mini", "Autonom")
    add_event(run_id, "analyze", "Start")
    finish_run(run_id, "done", "ok")

    runs = list_runs()
    assert any(r["run_id"] == run_id for r in runs)

    run = get_run(run_id)
    assert run is not None
    assert run["status"] == "done"


def test_event_order_is_preserved() -> None:
    run_id = create_run("Task B", "gpt-5.4-mini", "Autonom")
    add_event(run_id, "analyze", "1")
    add_event(run_id, "plan", "2")
    add_event(run_id, "patch", "3")

    run = get_run(run_id)
    assert [e["event_type"] for e in run["events"]] == ["analyze", "plan", "patch"]


def test_long_logs_and_secrets_are_sanitized() -> None:
    run_id = create_run("Task C", "gpt-5.4-mini", "Autonom")
    long_secret = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890" + ("x" * 5000)
    add_event(run_id, "error", "secret", {"log": long_secret})

    run = get_run(run_id)
    payload = str(run["events"][0]["data"])
    assert "sk-" not in payload
    assert "[REDACTED]" in payload
    assert len(payload) < 4300


def test_run_metrics_are_aggregated_on_finish() -> None:
    run_id = create_run("Task metrics", "gpt-5.4-mini", "Autonom", profile="review")
    add_event(run_id, "tool_decision", "Tools", {"use_search": True, "use_tests": True, "use_files": True, "use_plugins": False})
    add_event(
        run_id,
        "diff",
        "diff a.py",
        {"file": "a.py", "added_lines": 3, "removed_lines": 1, "hunks_count": 1, "risk_level": "low", "rollback_id": "rb-1"},
    )
    add_event(
        run_id,
        "approval_required",
        "needs approval",
        {"file": "b.py", "added_lines": 2, "removed_lines": 2, "hunks_count": 1, "risk_level": "medium"},
    )
    add_event(
        run_id,
        "approval_applied",
        "applied",
        {"file": "b.py", "added_lines": 2, "removed_lines": 2, "hunks_count": 1, "risk_level": "medium", "rollback_id": "rb-2"},
    )
    add_event(run_id, "test", "tests", {"ok": True})
    finish_run(run_id, "done", "ok")

    run = get_run(run_id)
    metrics = run["metrics"]
    assert metrics["final_status"] == "success"
    assert metrics["files_changed_count"] == 2
    assert metrics["approvals_requested"] == 1
    assert metrics["approvals_applied"] == 1
    assert metrics["patches_applied"] >= 1
    assert metrics["profile"] == "review"


def test_run_phase_is_updated_and_visible_live() -> None:
    run_id = create_run("Task phase", "gpt-5.4-mini", "Autonom")
    set_run_phase(run_id, "planning")
    add_event(run_id, "plan", "Planning")
    set_run_phase(run_id, "patching")
    add_event(run_id, "diff", "diff a.py", {"file": "a.py", "added_lines": 1, "removed_lines": 0, "hunks_count": 1})

    run = get_run(run_id)
    assert run is not None
    assert run["phase"] == "patching"
    assert run["metrics"]["current_phase"] == "patching"
    assert run["metrics"]["files_changed_count"] >= 1
    assert run["metrics"]["final_status"] in {"running", "approval_required"}


def test_run_phase_defaults_to_approval_required_from_events() -> None:
    run_id = create_run("Task approval phase", "gpt-5.4-mini", "Autonom")
    add_event(
        run_id,
        "approval_required",
        "Needs approval",
        {"file": "a.py", "patch": {"file_path": "a.py", "unified_diff": "@@ -1 +1 @@"}},
    )
    run = get_run(run_id)
    assert run is not None
    assert run["phase"] == "approval_required"


def test_policy_events_are_aggregated_in_metrics() -> None:
    run_id = create_run("Task policy metrics", "gpt-5.4-mini", "Autonom")
    add_event(run_id, "policy_warning", "w", {"reason": "allow_shell"})
    add_event(run_id, "policy_block", "b", {"reason": "allow_delete"})
    add_event(run_id, "policy_approval_required", "a", {"reason": "max_risk_level"})
    finish_run(run_id, "failed", "policy")
    run = get_run(run_id)
    metrics = run["metrics"]
    assert metrics["policy_warnings_count"] == 1
    assert metrics["policy_violations_count"] >= 2
    assert metrics["blocked_actions_count"] >= 1
    assert "allow_delete" in metrics["policy_trigger_reasons"]
