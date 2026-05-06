from packages.core.task_runs import add_event, create_run, get_run


def test_run_events_have_deterministic_sequence_and_snapshots() -> None:
    run_id = create_run("Replay", "gpt-5.4-mini", "Autonom")
    add_event(run_id, "plan", "p1", {"x": 1})
    add_event(run_id, "diff", "d1", {"file": "a.py", "added_lines": 1, "removed_lines": 0})
    run = get_run(run_id)
    assert run is not None
    events = run["events"]
    assert [e["sequence"] for e in events] == [1, 2]
    assert all("phase" in e for e in events)
    assert all("status" in e for e in events)
    assert all(isinstance(e.get("metrics_snapshot"), dict) for e in events)
    replay = run.get("replay", {})
    assert replay.get("total_events") == 2
    assert replay.get("first_sequence") == 1
    assert replay.get("last_sequence") == 2
    assert isinstance(replay.get("phase_sections"), list)


def test_checkpoints_are_created_and_sorted() -> None:
    from packages.core.task_runs import create_checkpoint, set_run_phase

    run_id = create_run("Checkpoint", "gpt-5.4-mini", "Autonom")
    set_run_phase(run_id, "planning")
    add_event(run_id, "plan", "p")
    create_checkpoint(run_id, reason="manual")
    set_run_phase(run_id, "patching")
    run = get_run(run_id)
    cps = run.get("checkpoints", [])
    assert len(cps) >= 2
    seqs = [int(cp.get("sequence", 0)) for cp in cps]
    assert seqs == sorted(seqs)
    assert all(cp.get("checkpoint_id") for cp in cps)
    assert run.get("resume_state", {}).get("state") in {"resumable", "waiting_for_approval"}
