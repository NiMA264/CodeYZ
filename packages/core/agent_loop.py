import json
from collections.abc import Callable
from typing import Any

from openai import OpenAI

from packages.core.settings import ALLOWED_MODELS, get_default_model, get_openai_api_key
from packages.core.agent_pipeline import run_multi_agent_task
from packages.core.executor import run_build, run_tests, summarize_errors
from packages.core.policy import evaluate_constraints, resolve_policy
from packages.core.patcher import (
    PatchApprovalRequired,
    apply_ast_patch,
    apply_patch,
    apply_unified_diff,
    build_diff_metadata,
)
from packages.core.permissions import assert_can_run_autonomous
from packages.core.task_runs import add_event, create_checkpoint, create_run, finish_run, get_run, set_run_phase
from packages.tools.files import list_files, read_file

MODEL = get_default_model()
SYSTEM = """
You are CodeYZ autonomous coding agent.
Rules:
- Small safe changes only.
- Never commit, push, deploy.
- Return strict JSON only.
""".strip()


def _emit_constraint_events(run_id: str, result: dict[str, object], *, role: str = "reviewer") -> None:
    warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    violations = result.get("violations") if isinstance(result.get("violations"), list) else []
    for item in warnings:
        if not isinstance(item, dict):
            continue
        add_event(run_id, "policy_warning", "Policy warning", {"reason": item.get("constraint"), "constraint_result": result}, agent_role=role)
    for item in violations:
        if not isinstance(item, dict):
            continue
        if str(item.get("severity")) == "blocked":
            add_event(run_id, "policy_block", "Policy blocked action", {"reason": item.get("constraint"), "constraint_result": result}, agent_role=role)
        else:
            add_event(run_id, "policy_approval_required", "Policy requires approval", {"reason": item.get("constraint"), "constraint_result": result}, agent_role=role)


def _client() -> OpenAI:
    return OpenAI(api_key=get_openai_api_key())


def _project_snapshot() -> str:
    files = [f for f in list_files(".") if f.endswith((".py", ".md", ".toml", ".json", ".css", ".js", ".html"))]
    top = files[:80]
    parts: list[str] = []
    for path in top[:15]:
        try:
            parts.append(f"FILE: {path}\n" + read_file(path, max_chars=1500))
        except Exception:
            continue
    return "\n\n".join(parts)


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON payload returned")
    return json.loads(raw[start : end + 1])


def _plan_and_patch(task: str, error_context: str = "", model: str | None = None) -> dict[str, Any]:
    snapshot = _project_snapshot()
    prompt = f"""
Task: {task}

Error context:
{error_context or 'none'}

Project snapshot:
{snapshot}

Return JSON with keys:
- plan: short string
- patches: array of objects with one of:
  - {{"file_path": "...", "ast_patch": {{"operation": "replace_function|add_function", "target": "function_name", "code": "def ..."}}}}
  - {{"file_path": "...", "unified_diff": "..."}}
  - {{"file_path": "...", "new_content": "..."}}
  - prefer ast_patch for simple Python function edits
  - fallback to unified_diff or new_content only if needed
Limit patches to at most 3 files.
"""
    selected_model = model if model in ALLOWED_MODELS else MODEL
    response = _client().responses.create(
        model=selected_model,
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return _extract_json(response.output_text)


def run_autonomous_task(
    task: str,
    model: str | None = None,
    access_level: str | None = None,
    use_multi_agent: bool = False,
    max_cost_usd: float | None = None,
    profile: str | None = None,
    request_id: str | None = None,
    run_id: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    effective_policy = resolve_policy(profile)
    if use_multi_agent:
        pre = evaluate_constraints(
            policy=effective_policy,
            runtime={"wants_multi_agent": True},
            action="multi_agent",
        )
        if bool(pre.get("blocked")):
            return {"ok": False, "run_id": "", "error": "Policy blocks multi-agent mode", "events": []}
        return run_multi_agent_task(
            task=task,
            access_level=access_level,
            model=model,
            max_cost_usd=max_cost_usd,
            profile=profile,
            request_id=request_id,
        )

    if run_id is None:
        run_id = create_run(
            task=task,
            model=model,
            access_level=access_level,
            profile=profile,
            policy=effective_policy,
            request_id=request_id,
        )
    set_run_phase(run_id, "analyzing")
    add_event(run_id, "analyze", "Autonomous task started", {"task": task, "policy": effective_policy})

    try:
        assert_can_run_autonomous(access_level)
    except PermissionError as exc:
        add_event(run_id, "error", "Access denied", {"error": str(exc)})
        set_run_phase(run_id, "failed")
        finish_run(run_id, "blocked", str(exc))
        run = get_run(run_id)
        return {"ok": False, "run_id": run_id, "error": str(exc), "events": run["events"] if run else []}

    logs: list[dict[str, Any]] = []
    last_error = ""
    cancel_check = should_cancel or (lambda: False)

    for iteration in range(1, 6):
        if cancel_check():
            add_event(run_id, "cancel", "Run cancellation requested", {"iteration": iteration})
            set_run_phase(run_id, "cancelled")
            finish_run(run_id, "cancelled", "Run cancelled")
            run = get_run(run_id)
            return {"ok": False, "run_id": run_id, "error": "Run cancelled", "events": run["events"] if run else []}
        run_state = get_run(run_id) or {}
        runtime_eval = evaluate_constraints(policy=effective_policy, run_state=run_state, action="runtime")
        if bool(runtime_eval.get("blocked")):
            _emit_constraint_events(run_id, runtime_eval)
            set_run_phase(run_id, "failed")
            finish_run(run_id, "failed", "Policy runtime limit exceeded")
            run = get_run(run_id)
            return {"ok": False, "run_id": run_id, "error": "Policy runtime limit exceeded", "events": run["events"] if run else []}

        step: dict[str, Any] = {"iteration": iteration}
        set_run_phase(run_id, "planning")
        add_event(run_id, "plan", f"Iteration {iteration}: planning")

        plan_payload = _plan_and_patch(task, last_error, model=model)
        plan_text = plan_payload.get("plan", "")
        step["plan"] = plan_text
        add_event(run_id, "plan", f"Iteration {iteration}: plan ready", {"plan": plan_text})

        patch_results: list[dict[str, str]] = []
        set_run_phase(run_id, "patching")
        for patch in plan_payload.get("patches", [])[:3]:
            if cancel_check():
                add_event(run_id, "cancel", "Run cancellation requested", {"iteration": iteration, "stage": "patching"})
                set_run_phase(run_id, "cancelled")
                finish_run(run_id, "cancelled", "Run cancelled")
                run = get_run(run_id)
                return {"ok": False, "run_id": run_id, "error": "Run cancelled", "events": run["events"] if run else []}
            file_path = str(patch.get("file_path", "")).strip()
            ast_patch = patch.get("ast_patch")
            unified_diff = str(patch.get("unified_diff", "")).strip()
            new_content = str(patch.get("new_content", ""))
            if not file_path:
                continue
            try:
                approved = bool(not effective_policy.get("require_approval", False))
                if isinstance(ast_patch, dict):
                    patch_result = apply_ast_patch(
                        file_path,
                        operation=str(ast_patch.get("operation", "")),
                        target=str(ast_patch.get("target", "")),
                        code=str(ast_patch.get("code", "")),
                        access_level=access_level,
                        approved=approved,
                    )
                elif unified_diff:
                    patch_result = apply_unified_diff(file_path, unified_diff, access_level=access_level, approved=approved)
                else:
                    patch_result = apply_patch(file_path, new_content, access_level=access_level, approved=approved)

                patch_results.append(patch_result)
                add_event(run_id, "patch", f"Iteration {iteration}: patched {file_path}", {"file": file_path, "rollback_id": patch_result.get("rollback_id")})
                add_event(
                    run_id,
                    "diff",
                    f"Iteration {iteration}: diff for {file_path}",
                    {
                        "diff": patch_result.get("diff", ""),
                        "rollback_id": patch_result.get("rollback_id"),
                        "file": patch_result.get("file", file_path),
                        "file_status": patch_result.get("file_status", "unknown"),
                        "hunks_count": patch_result.get("hunks_count", 0),
                        "added_lines": patch_result.get("added_lines", 0),
                        "removed_lines": patch_result.get("removed_lines", 0),
                        "risk_level": patch_result.get("risk_level", "unknown"),
                        "approval_required": bool(patch_result.get("approval_required", False)),
                        "files_changed_count": patch_result.get("files_changed_count", 1),
                    },
                )
                current = get_run(run_id) or {}
                live_metrics = current.get("metrics", {}) if isinstance(current.get("metrics"), dict) else {}
                patch_eval = evaluate_constraints(
                    policy=effective_policy,
                    metrics=live_metrics,
                    run_state=current,
                    patch_meta={
                        "file_status": patch_result.get("file_status", "unknown"),
                        "risk_level": patch_result.get("risk_level", "unknown"),
                    },
                    action="patch",
                )
                if bool(patch_eval.get("blocked")) or bool(patch_eval.get("requires_approval")):
                    _emit_constraint_events(run_id, patch_eval)
                if bool(patch_eval.get("requires_approval")):
                    set_run_phase(run_id, "approval_required")
                if bool(patch_eval.get("blocked")):
                    set_run_phase(run_id, "failed")
                    finish_run(run_id, "failed", "Policy blocked patch")
                    run = get_run(run_id)
                    return {"ok": False, "run_id": run_id, "error": "Policy blocked patch", "events": run["events"] if run else []}
            except PatchApprovalRequired as exc:
                patch_payload = {"file_path": file_path}
                if unified_diff:
                    patch_payload["unified_diff"] = unified_diff
                elif isinstance(ast_patch, dict):
                    patch_payload["ast_patch"] = ast_patch
                else:
                    patch_payload["new_content"] = new_content
                preview = exc.patch_text or unified_diff or str(ast_patch) or new_content
                meta = build_diff_metadata(
                    exc.file_path or file_path,
                    preview,
                    is_new_file=bool(exc.stats.get("is_new_file")) if isinstance(exc.stats, dict) else False,
                    risk_level=exc.risk_level,
                    approval_required=True,
                )
                approval_payload = {
                    "file": exc.file_path or file_path,
                    "risk_level": exc.risk_level,
                    "reasons": exc.reasons,
                    "stats": exc.stats,
                    "patch_preview": preview[:1000],
                    "patch": patch_payload,
                    "policy_reason": "require_approval",
                    "policy": effective_policy,
                    **meta,
                }
                cp = create_checkpoint(run_id, reason="before_approval_required", current_action="approval_required")
                approval_payload["checkpoint_before_approval"] = cp.get("checkpoint_id", "") if isinstance(cp, dict) else ""
                approval_payload["resumable_phase"] = cp.get("phase", "approval_required") if isinstance(cp, dict) else "approval_required"
                approval_payload["resume_sequence"] = int(cp.get("sequence", 0) or 0) if isinstance(cp, dict) else 0
                patch_results.append({"file": file_path, "diff": "", "archive": "", "error": str(exc)})
                set_run_phase(run_id, "approval_required")
                add_event(run_id, "policy_approval_required", "Policy requires approval", {"reason": "require_approval", "file": file_path})
                add_event(run_id, "approval_required", "High-risk patch requires approval", approval_payload)
            except Exception as exc:
                error_result = {"file": file_path, "diff": "", "archive": "", "error": str(exc)}
                patch_results.append(error_result)
                add_event(run_id, "error", f"Iteration {iteration}: patch failed", error_result)

        step["patches"] = patch_results

        set_run_phase(run_id, "testing")
        shell_eval = evaluate_constraints(
            policy=effective_policy,
            run_state=get_run(run_id) or {},
            runtime={"wants_shell": True},
            action="shell",
        )
        if not bool(shell_eval.get("blocked")) and not bool(shell_eval.get("warnings")) and bool(effective_policy.get("allow_shell", False)):
            if cancel_check():
                add_event(run_id, "cancel", "Run cancellation requested", {"iteration": iteration, "stage": "testing"})
                set_run_phase(run_id, "cancelled")
                finish_run(run_id, "cancelled", "Run cancelled")
                run = get_run(run_id)
                return {"ok": False, "run_id": run_id, "error": "Run cancelled", "events": run["events"] if run else []}
            build_result = run_build(access_level=access_level)
            test_result = run_tests(access_level=access_level)
        else:
            _emit_constraint_events(run_id, shell_eval, role="tester")
            build_result = {"ok": False, "output": "Build disabled by policy (allow_shell=false)"}
            test_result = {"ok": False, "output": "Tests disabled by policy (allow_shell=false)"}

        step["build"] = build_result
        step["tests"] = test_result
        add_event(run_id, "build", f"Iteration {iteration}: build", build_result)
        add_event(run_id, "test", f"Iteration {iteration}: tests", test_result)

        if bool(build_result.get("ok")) and bool(test_result.get("ok")):
            step["status"] = "done"
            logs.append(step)
            add_event(run_id, "result", "Autonomous task finished", {"status": "done", "iteration": iteration})
            set_run_phase(run_id, "completed")
            finish_run(run_id, "done", "Build and tests passed")
            run = get_run(run_id)
            return {"ok": True, "run_id": run_id, "iterations": logs, "events": run["events"] if run else []}

        test_eval = evaluate_constraints(
            policy=effective_policy,
            run_state=get_run(run_id) or {},
            runtime={"wants_tests": True, "tests_ok": bool(test_result.get("ok"))},
            action="tests",
        )
        if bool(test_eval.get("requires_approval")) or bool(test_eval.get("blocked")):
            _emit_constraint_events(run_id, test_eval, role="tester")

        step["status"] = "needs_fix"
        last_error = summarize_errors(str(build_result.get("output", "")), str(test_result.get("output", "")))
        step["error_summary"] = last_error
        logs.append(step)
        add_event(run_id, "fix", f"Iteration {iteration}: fix needed", {"error_summary": last_error})

    add_event(run_id, "result", "Autonomous task reached iteration limit", {"status": "failed"})
    set_run_phase(run_id, "failed")
    finish_run(run_id, "failed", "Max iterations reached")
    run = get_run(run_id)
    return {
        "ok": False,
        "run_id": run_id,
        "iterations": logs,
        "events": run["events"] if run else [],
        "error": "Max iterations reached",
    }
