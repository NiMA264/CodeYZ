from __future__ import annotations


def test_task_runs_public_imports_work() -> None:
    from packages.core.task_runs import add_event, create_run, get_run

    run_id = create_run("compat", "gpt-5.4-mini", "Autonom")
    add_event(run_id, "analyze", "ok")
    run = get_run(run_id)
    assert run is not None
    assert run["run_id"] == run_id


def test_task_runs_submodules_importable() -> None:
    from packages.core.task_runs import events, lifecycle, metrics, replay, resume, storage

    assert hasattr(events, "add_event")
    assert hasattr(lifecycle, "create_run")
    assert hasattr(metrics, "create_checkpoint")
    assert hasattr(replay, "get_run")
    assert hasattr(resume, "execute_resume")
    assert hasattr(storage, "initialize_task_runs_storage")
