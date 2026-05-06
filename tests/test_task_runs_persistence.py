from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from pathlib import Path


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


def test_task_runs_persist_approval_states_across_reload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs = importlib.reload(task_runs_module)
    run_id = runs.create_run("approval persist", "gpt-5.4-mini", "Autonom")
    source_event_id = "evt-approval-1"

    assert runs.claim_approval_event(run_id, source_event_id) is True
    runs.mark_approval_event(run_id, source_event_id, "applied")

    runs_reloaded = importlib.reload(task_runs_module)
    runs_reloaded.initialize_task_runs_storage()

    assert runs_reloaded.claim_approval_event(run_id, source_event_id) is False


def test_task_runs_old_records_without_approval_states_are_compatible(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs_file = tmp_path / "runs" / "runs.jsonl"
    _write_jsonl(
        runs_file,
        [
            {
                "kind": "run_created",
                "run_id": "run-old-1",
                "task": "legacy",
                "ts": "2026-01-01T00:00:00+00:00",
            },
            {
                "kind": "event",
                "run_id": "run-old-1",
                "event_id": "evt-1",
                "event_type": "approval_applied",
                "agent_role": "reviewer",
                "title": "Approved patch applied",
                "data": {"source_event_id": "evt-legacy", "file": "a.py"},
                "ts": "2026-01-01T00:00:01+00:00",
            },
        ],
    )

    runs = importlib.reload(task_runs_module)
    runs.initialize_task_runs_storage()

    run = runs.get_run("run-old-1")
    assert run is not None
    assert run["task"] == "legacy"
    assert runs.has_approval_applied("run-old-1", "evt-legacy") is True
    assert isinstance(run.get("metrics", {}), dict)


def test_task_runs_persist_metrics_in_run_finished_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs = importlib.reload(task_runs_module)
    run_id = runs.create_run("metrics persist", "gpt-5.4-mini", "Autonom", profile="fast_fix")
    runs.add_event(run_id, "diff", "d", {"file": "a.py", "added_lines": 1, "removed_lines": 0, "hunks_count": 1})
    runs.finish_run(run_id, "done", "ok")

    runs_file = tmp_path / "runs" / "runs.jsonl"
    lines = runs_file.read_text(encoding="utf-8").splitlines()
    finished = [json.loads(line) for line in lines if "\"kind\": \"run_finished\"" in line]
    assert finished
    assert "metrics" in finished[-1]
    assert finished[-1]["metrics"]["files_changed_count"] >= 1


def test_compact_runs_storage_reduces_redundant_approval_state_records(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs_file = tmp_path / "runs" / "runs.jsonl"
    _write_jsonl(
        runs_file,
        [
            {"kind": "run_created", "run_id": "run-1", "task": "t", "ts": "2026-01-01T00:00:00+00:00"},
            {"kind": "approval_state", "run_id": "run-1", "source_event_id": "evt-1", "status": "claimed", "ts": "2026-01-01T00:00:01+00:00"},
            {"kind": "approval_state", "run_id": "run-1", "source_event_id": "evt-1", "status": "failed", "ts": "2026-01-01T00:00:02+00:00"},
            {"kind": "approval_state", "run_id": "run-1", "source_event_id": "evt-1", "status": "applied", "ts": "2026-01-01T00:00:03+00:00"},
        ],
    )

    runs = importlib.reload(task_runs_module)
    before_count = sum(1 for line in runs_file.read_text(encoding="utf-8").splitlines() if '"kind": "approval_state"' in line)
    assert before_count == 3

    runs.compact_runs_storage()
    compacted_lines = runs_file.read_text(encoding="utf-8").splitlines()
    after_count = sum(1 for line in compacted_lines if '"kind": "approval_state"' in line)
    assert after_count == 0
    assert sum(1 for line in compacted_lines if '"kind": "run_created"' in line) == 1

    reloaded = importlib.reload(task_runs_module)
    reloaded.initialize_task_runs_storage()
    assert reloaded.claim_approval_event("run-1", "evt-1") is False


def test_compact_runs_storage_keeps_events_and_ignores_corrupt_lines(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs_file = tmp_path / "runs" / "runs.jsonl"
    runs_file.parent.mkdir(parents=True, exist_ok=True)
    runs_file.write_text(
        "\n".join(
            [
                json.dumps({"kind": "run_created", "run_id": "run-2", "task": "legacy", "ts": "2026-01-01T00:00:00+00:00"}),
                "{broken-json",
                json.dumps(
                    {
                        "kind": "event",
                        "run_id": "run-2",
                        "event_id": "evt-a",
                        "event_type": "plan",
                        "agent_role": "planner",
                        "title": "Plan ready",
                        "data": {"x": 1},
                        "ts": "2026-01-01T00:00:01+00:00",
                    }
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    runs = importlib.reload(task_runs_module)
    runs.compact_runs_storage()

    reloaded = importlib.reload(task_runs_module)
    reloaded.initialize_task_runs_storage()
    run = reloaded.get_run("run-2")
    assert run is not None
    assert len(run["events"]) == 1
    assert run["events"][0]["event_type"] == "plan"


def test_task_runs_lock_is_reentrant_for_compact_and_append(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs = importlib.reload(task_runs_module)
    run_id = runs.create_run("lock", "gpt-5.4-mini", "Autonom")
    runs.add_event(run_id, "plan", "x")

    with runs._LOCK:
        runs.compact_runs_storage()
        runs.mark_approval_event(run_id, "evt-lock", "claimed")

    reloaded = importlib.reload(task_runs_module)
    reloaded.initialize_task_runs_storage()
    assert reloaded.claim_approval_event(run_id, "evt-lock") is False


def test_lock_file_path_is_derived_next_to_target(tmp_path: Path) -> None:
    from packages.core.persistence import lock_file_path

    target = tmp_path / "runs" / "runs.jsonl"
    lock = lock_file_path(target)
    assert lock == tmp_path / "runs" / "runs.jsonl.lock"


def test_task_runs_uses_file_lock_for_append_and_compact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import task_runs as task_runs_module

    runs = importlib.reload(task_runs_module)
    calls: list[str] = []

    @contextmanager
    def fake_file_lock(_path: Path):
        calls.append("lock")
        yield

    monkeypatch.setattr(runs, "file_lock", fake_file_lock)

    run_id = runs.create_run("file-lock", "gpt-5.4-mini", "Autonom")
    runs.add_event(run_id, "plan", "x")
    runs.compact_runs_storage()

    assert len(calls) >= 3
