from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from packages.core.agent_loop import run_autonomous_task
from packages.core.job_queue import get_job_queue
from packages.core.loop import run_task
from packages.core.model_router import set_role_models
from packages.core.policy import resolve_policy
from packages.core.patcher import apply_patch, apply_unified_diff
from packages.core.permissions import can_run_autonomous
from packages.core.task_runs import (
    add_event,
    claim_approval_event,
    create_checkpoint,
    create_run,
    get_event,
    get_run,
    has_approval_applied,
    list_runs,
    mark_approval_event,
    set_run_phase,
    execute_resume,
)
from packages.server.errors import raise_api_error

router = APIRouter(prefix="/task", tags=["task"])


class TaskRequest(BaseModel):
    task: str
    model: str | None = None
    access_level: str | None = None
    profile: str | None = None
    multi_agent: bool | None = None
    max_cost_usd: float | None = None
    role_models: dict[str, str] | None = None


class ResumeRequest(BaseModel):
    checkpoint_id: str | None = None
    target_phase: str | None = None


@router.post("")
def task(payload: TaskRequest) -> dict[str, str]:
    return {"result": run_task(payload.task)}


@router.post("/auto")
def task_auto(payload: TaskRequest, request: Request) -> dict:
    if payload.role_models:
        try:
            set_role_models(payload.role_models)
        except ValueError as exc:
            raise_api_error(400, "invalid_role_models", str(exc), "Use only allowed model names per role.")

    if not can_run_autonomous(payload.access_level):
        raise_api_error(
            status.HTTP_403_FORBIDDEN,
            "autonomous_access_denied",
            "Access denied: /task/auto requires access level 'Autonom'",
            "Set access level to 'Autonom' in Composer or request payload.",
        )
    request_id = str(getattr(request.state, "request_id", ""))
    run_id = create_run(
        task=payload.task,
        model=payload.model,
        access_level=payload.access_level,
        profile=payload.profile,
        policy=resolve_policy(payload.profile),
        request_id=request_id,
    )
    queue = get_job_queue()
    queued = queue.enqueue(
        run_id=run_id,
        request_id=request_id,
        execute=lambda should_cancel: run_autonomous_task(
            payload.task,
            model=payload.model,
            access_level=payload.access_level,
            profile=payload.profile,
            use_multi_agent=bool(payload.multi_agent),
            max_cost_usd=payload.max_cost_usd,
            request_id=request_id,
            run_id=run_id,
            should_cancel=should_cancel,
        ),
    )
    return {"ok": True, "run_id": run_id, "job_id": queued["job_id"], "state": queued["state"]}


@router.post("/cancel/{run_id}")
def task_cancel(run_id: str) -> dict[str, str]:
    run = get_run(run_id)
    if run is None:
        raise_api_error(404, "run_not_found", "Run not found", "List runs via GET /task/runs first.")
    result = get_job_queue().cancel(run_id)
    if result.get("state") == "missing":
        raise_api_error(409, "cancel_not_possible", "Run is not cancellable", "Run is already completed or unknown to worker.")
    return result


@router.get("/runs")
def task_runs() -> dict:
    return {"runs": list_runs()}


@router.get("/policy/{profile}")
def task_policy(profile: str) -> dict:
    return {"profile": profile, "policy": resolve_policy(profile)}


@router.get("/runs/{run_id}")
def task_run_by_id(run_id: str) -> dict:
    run = get_run(run_id)
    if run is None:
        raise_api_error(404, "run_not_found", "Run not found", "List runs via GET /task/runs first.")
    return run


@router.get("/runs/{run_id}/resume-validation")
def task_resume_validation(run_id: str, checkpoint_id: str | None = None, target_phase: str | None = None) -> dict:
    from packages.core.task_runs import validate_resume_transition

    validation = validate_resume_transition(run_id, checkpoint_id=checkpoint_id, target_phase=target_phase)
    if "missing_run" in validation.get("blocking_conditions", []):
        raise_api_error(404, "run_not_found", "Run not found", "List runs via GET /task/runs first.")
    return {"run_id": run_id, "validation": validation}


@router.post("/resume/{run_id}")
def task_resume(run_id: str, payload: ResumeRequest | None = None) -> dict:
    result = execute_resume(
        run_id,
        checkpoint_id=(payload.checkpoint_id if payload else None),
        target_phase=(payload.target_phase if payload else None),
    )
    validation = result.get("validation", {})
    if "missing_run" in validation.get("blocking_conditions", []):
        raise_api_error(404, "run_not_found", "Run not found", "List runs via GET /task/runs first.")
    if not result.get("ok"):
        raise_api_error(
            409,
            "resume_rejected",
            "Run resume was rejected by validation.",
            f"Blocking conditions: {', '.join(validation.get('blocking_conditions', [])) or 'unknown'}",
        )
    return result


@router.post("/runs/{run_id}/approve-patch/{event_id}")
def approve_patch(run_id: str, event_id: str) -> dict:
    run = get_run(run_id)
    if run is None:
        raise_api_error(404, "run_not_found", "Run not found", "List runs via GET /task/runs first.")

    event = get_event(run_id, event_id)
    if event is None:
        raise_api_error(404, "event_not_found", "Event not found", "Use an event_id from GET /task/runs/{run_id}.")
    if event.get("event_type") != "approval_required":
        raise_api_error(
            400,
            "event_not_approvable",
            "Only approval_required events can be approved.",
            "Select an approval_required event from the timeline.",
        )
    if has_approval_applied(run_id, event_id):
        raise_api_error(
            409,
            "approval_already_applied",
            "This approval-required patch was already applied.",
            "Reload timeline and use the latest run state.",
        )
    if not claim_approval_event(run_id, event_id):
        raise_api_error(
            409,
            "approval_already_claimed",
            "This approval-required patch is already being processed or was already applied.",
            "Reload timeline and wait for the current approval result.",
        )

    set_run_phase(run_id, "approval_required")
    checkpoint_before = create_checkpoint(run_id, reason="before_approval_apply", current_action="approval_wait")
    data = event.get("data") or {}
    patch = data.get("patch") if isinstance(data, dict) else None
    if not isinstance(patch, dict):
        raise_api_error(400, "approval_patch_missing", "Stored patch payload missing.", "Retry task to regenerate approval event.")

    file_path = str(patch.get("file_path", "")).strip()
    unified_diff = str(patch.get("unified_diff", "")).strip()
    new_content = patch.get("new_content")
    if not file_path or (not unified_diff and not isinstance(new_content, str)):
        raise_api_error(400, "approval_patch_invalid", "Stored patch payload is invalid.", "Retry task to regenerate approval event.")

    try:
        set_run_phase(run_id, "applying")
        if unified_diff:
            out = apply_unified_diff(file_path, unified_diff, access_level="Autonom", approved=True)
        else:
            out = apply_patch(file_path, str(new_content), access_level="Autonom", approved=True)
    except Exception as exc:
        mark_approval_event(run_id, event_id, "failed")
        set_run_phase(run_id, "failed")
        add_event(
            run_id,
            "error",
            "Approval apply failed",
            {"source_event_id": event_id, "file": file_path, "error": str(exc)},
            agent_role="reviewer",
        )
        raise_api_error(400, "approval_apply_failed", str(exc), "Review the stored patch and file context, then retry.")

    payload = {
        "source_event_id": event_id,
        "file": file_path,
        "risk_level": str(data.get("risk_level", "high")),
        "reasons": data.get("reasons", []),
        "stats": data.get("stats", {}),
        "diff": out.get("diff", ""),
        "rollback_id": out.get("rollback_id", ""),
        "file_status": out.get("file_status", data.get("file_status", "unknown")),
        "hunks_count": out.get("hunks_count", data.get("hunks_count", 0)),
        "added_lines": out.get("added_lines", data.get("added_lines", 0)),
        "removed_lines": out.get("removed_lines", data.get("removed_lines", 0)),
        "approval_required": False,
        "files_changed_count": out.get("files_changed_count", data.get("files_changed_count", 1)),
        "checkpoint_before_approval": (checkpoint_before or {}).get("checkpoint_id", ""),
        "resumable_phase": (checkpoint_before or {}).get("phase", "approval_required"),
        "resume_sequence": int((checkpoint_before or {}).get("sequence", 0) or 0),
    }
    applied_event = add_event(run_id, "approval_applied", "Approved patch applied", payload, agent_role="reviewer")
    create_checkpoint(run_id, reason="after_approval_applied", current_action="approval_applied")
    mark_approval_event(run_id, event_id, "applied")
    return {"ok": True, "run_id": run_id, "event": applied_event, "result": out}
