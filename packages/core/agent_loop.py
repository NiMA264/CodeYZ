import json
import os
from typing import Any

from openai import OpenAI

from packages.core.agent_pipeline import run_multi_agent_task
from packages.core.executor import run_build, run_tests, summarize_errors
from packages.core.patcher import (
    PatchApprovalRequired,
    apply_ast_patch,
    apply_patch,
    apply_unified_diff,
    build_diff_metadata,
)
from packages.core.permissions import assert_can_run_autonomous
from packages.core.task_runs import add_event, create_run, finish_run, get_run
from packages.tools.files import list_files, read_file

MODEL = os.getenv("CODEYZ_MODEL", "gpt-5.4-mini")
ALLOWED_MODELS = {"gpt-5.4-mini", "gpt-5.4", "gpt-5.5"}
SYSTEM = """
You are CodeYZ autonomous coding agent.
Rules:
- Small safe changes only.
- Never commit, push, deploy.
- Return strict JSON only.
""".strip()


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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
  - {"file_path": "...", "ast_patch": {"operation": "replace_function|add_function", "target": "function_name", "code": "def ..."}}
  - {"file_path": "...", "unified_diff": "..."}
  - {"file_path": "...", "new_content": "..."}
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
) -> dict[str, Any]:
    if use_multi_agent:
        return run_multi_agent_task(task=task, access_level=access_level, model=model, max_cost_usd=max_cost_usd, profile=profile)

    run_id = create_run(task=task, model=model, access_level=access_level, profile=profile)
    add_event(run_id, "analyze", "Autonomous task started", {"task": task})

    try:
        assert_can_run_autonomous(access_level)
    except PermissionError as exc:
        add_event(run_id, "error", "Access denied", {"error": str(exc)})
        finish_run(run_id, "blocked", str(exc))
        run = get_run(run_id)
        return {"ok": False, "run_id": run_id, "error": str(exc), "events": run["events"] if run else []}

    logs: list[dict[str, Any]] = []
    last_error = ""

    for iteration in range(1, 6):
        step: dict[str, Any] = {"iteration": iteration}
        add_event(run_id, "plan", f"Iteration {iteration}: planning")

        plan_payload = _plan_and_patch(task, last_error, model=model)
        plan_text = plan_payload.get("plan", "")
        step["plan"] = plan_text
        add_event(run_id, "plan", f"Iteration {iteration}: plan ready", {"plan": plan_text})

        patch_results: list[dict[str, str]] = []
        for patch in plan_payload.get("patches", [])[:3]:
            file_path = str(patch.get("file_path", "")).strip()
            ast_patch = patch.get("ast_patch")
            unified_diff = str(patch.get("unified_diff", "")).strip()
            new_content = str(patch.get("new_content", ""))
            if not file_path:
                continue
            try:
                if isinstance(ast_patch, dict):
                    patch_result = apply_ast_patch(
                        file_path,
                        operation=str(ast_patch.get("operation", "")),
                        target=str(ast_patch.get("target", "")),
                        code=str(ast_patch.get("code", "")),
                        access_level=access_level,
                    )
                elif unified_diff:
                    patch_result = apply_unified_diff(file_path, unified_diff, access_level=access_level)
                else:
                    patch_result = apply_patch(file_path, new_content, access_level=access_level)
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
                    **meta,
                }
                patch_results.append({"file": file_path, "diff": "", "archive": "", "error": str(exc)})
                add_event(run_id, "approval_required", "High-risk patch requires approval", approval_payload)
            except Exception as exc:
                error_result = {"file": file_path, "diff": "", "archive": "", "error": str(exc)}
                patch_results.append(error_result)
                add_event(run_id, "error", f"Iteration {iteration}: patch failed", error_result)

        step["patches"] = patch_results

        build_result = run_build(access_level=access_level)
        test_result = run_tests(access_level=access_level)
        step["build"] = build_result
        step["tests"] = test_result
        add_event(run_id, "build", f"Iteration {iteration}: build", build_result)
        add_event(run_id, "test", f"Iteration {iteration}: tests", test_result)

        if bool(build_result.get("ok")) and bool(test_result.get("ok")):
            step["status"] = "done"
            logs.append(step)
            add_event(run_id, "result", "Autonomous task finished", {"status": "done", "iteration": iteration})
            finish_run(run_id, "done", "Build and tests passed")
            run = get_run(run_id)
            return {"ok": True, "run_id": run_id, "iterations": logs, "events": run["events"] if run else []}

        step["status"] = "needs_fix"
        last_error = summarize_errors(str(build_result.get("output", "")), str(test_result.get("output", "")))
        step["error_summary"] = last_error
        logs.append(step)
        add_event(run_id, "fix", f"Iteration {iteration}: fix needed", {"error_summary": last_error})

    add_event(run_id, "result", "Autonomous task reached iteration limit", {"status": "failed"})
    finish_run(run_id, "failed", "Max iterations reached")
    run = get_run(run_id)
    return {
        "ok": False,
        "run_id": run_id,
        "iterations": logs,
        "events": run["events"] if run else [],
        "error": "Max iterations reached",
    }

