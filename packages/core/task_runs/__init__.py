from __future__ import annotations

import importlib
from typing import Any

from packages.core.task_runs import _impl as _task_runs_impl

_impl = importlib.reload(_task_runs_impl)
file_lock = _impl.file_lock
_LOCK = _impl._LOCK


def _sync_runtime_patches() -> None:
    _impl.file_lock = file_lock
    _impl._LOCK = _LOCK


def add_event(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.add_event(*args, **kwargs)


def claim_approval_event(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.claim_approval_event(*args, **kwargs)


def compact_runs_storage(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.compact_runs_storage(*args, **kwargs)


def create_checkpoint(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.create_checkpoint(*args, **kwargs)


def create_run(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.create_run(*args, **kwargs)


def execute_resume(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.execute_resume(*args, **kwargs)


def finish_run(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.finish_run(*args, **kwargs)


def get_event(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.get_event(*args, **kwargs)


def get_run(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.get_run(*args, **kwargs)


def has_approval_applied(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.has_approval_applied(*args, **kwargs)


def initialize_task_runs_storage(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.initialize_task_runs_storage(*args, **kwargs)


def list_runs(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.list_runs(*args, **kwargs)


def load_runs(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.load_runs(*args, **kwargs)


def mark_approval_event(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.mark_approval_event(*args, **kwargs)


def set_run_phase(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.set_run_phase(*args, **kwargs)


def validate_resume(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.validate_resume(*args, **kwargs)


def validate_resume_transition(*args: Any, **kwargs: Any):
    _sync_runtime_patches()
    return _impl.validate_resume_transition(*args, **kwargs)


__all__ = [
    "add_event",
    "claim_approval_event",
    "compact_runs_storage",
    "create_checkpoint",
    "create_run",
    "execute_resume",
    "file_lock",
    "finish_run",
    "get_event",
    "get_run",
    "has_approval_applied",
    "initialize_task_runs_storage",
    "list_runs",
    "load_runs",
    "mark_approval_event",
    "set_run_phase",
    "validate_resume",
    "validate_resume_transition",
    "_LOCK",
]
