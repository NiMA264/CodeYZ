from packages.core.task_runs import (
    add_event,
    create_checkpoint,
    create_run,
    execute_resume,
    finish_run,
    get_run,
    set_run_phase,
    validate_resume,
    validate_resume_transition,
)


def test_validate_resume_rejects_completed_run() -> None:
    run_id = create_run("resume completed", "gpt-5.4-mini", "Autonom")
    finish_run(run_id, "done", "ok")
    validation = validate_resume(run_id)
    assert validation["allowed"] is False
    assert "state_completed" in validation["blocking_conditions"]


def test_execute_resume_emits_resume_events_for_resumable_run() -> None:
    run_id = create_run("resume run", "gpt-5.4-mini", "Autonom")
    set_run_phase(run_id, "patching")
    add_event(run_id, "patch", "ready")
    create_checkpoint(run_id, reason="manual_resumable")
    result = execute_resume(run_id)
    assert result["ok"] is True
    run = get_run(run_id)
    event_types = [e["event_type"] for e in run["events"]]
    assert "resume_requested" in event_types
    assert "resume_phase_requested" in event_types
    assert "resume_phase_started" in event_types
    assert "resume_phase_completed" in event_types
    assert "resume_started" in event_types
    assert "resume_completed" in event_types


def test_execute_resume_rejected_when_pending_approval() -> None:
    run_id = create_run("resume pending approval", "gpt-5.4-mini", "Autonom")
    approval = add_event(
        run_id,
        "approval_required",
        "need approval",
        {"file": "a.py", "patch": {"file_path": "a.py", "unified_diff": "@@ -1 +1 @@"}},
    )
    create_checkpoint(run_id, reason="before_approval")
    result = execute_resume(run_id)
    assert result["ok"] is False
    assert "pending_approvals" in result["validation"]["blocking_conditions"]
    run = get_run(run_id)
    rejected = [e for e in run["events"] if e["event_type"] == "resume_rejected"]
    assert rejected
    assert approval["event_id"] in result["validation"]["resume_state"]["pending_approvals"]


def test_validate_resume_transition_rejects_invalid_target_phase() -> None:
    run_id = create_run("resume invalid target", "gpt-5.4-mini", "Autonom")
    create_checkpoint(run_id, reason="manual")
    validation = validate_resume_transition(run_id, target_phase="completed")
    assert validation["allowed"] is False
    assert "unsupported_source_phase" in validation["blocking_conditions"]


def test_resume_transition_limit_is_enforced() -> None:
    run_id = create_run("resume limit", "gpt-5.4-mini", "Autonom")
    set_run_phase(run_id, "patching")
    create_checkpoint(run_id, reason="manual")
    for _ in range(3):
        out = execute_resume(run_id)
        assert out["ok"] is True
    blocked = execute_resume(run_id)
    assert blocked["ok"] is False
    assert "resume_limit_reached" in blocked["validation"]["blocking_conditions"]
