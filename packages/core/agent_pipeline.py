from typing import Any

from packages.core.agents import coder, fixer, planner, reviewer, tester
from packages.core.costs import BudgetCheck
from packages.core.executor import run_build, run_tests, summarize_errors
from packages.core.indexer import search_files
from packages.core.patcher import (
    PatchApprovalRequired,
    apply_ast_patch,
    apply_patch,
    apply_unified_diff,
    build_diff_metadata,
)
from packages.core.plugins import call_plugin
from packages.core.permissions import (
    assert_can_run_autonomous,
    can_run_autonomous,
    can_run_tests,
    can_write_files,
)
from packages.core.task_runs import add_event, create_run, finish_run, get_run
from packages.core.tool_selector import decide_tools
from packages.tools.files import list_files
from packages.tools.git import git_diff


def _context_snapshot() -> str:
    files = list_files(".")[:120]
    return "\n".join(files)


def _normalize_role_output(raw, role: str, default_model: str | None) -> dict:
    if isinstance(raw, dict):
        out = dict(raw)
    else:
        out = {"output": str(raw)}
    out.setdefault("role", role)
    out.setdefault("model", default_model or "gpt-5.4-mini")
    out.setdefault("estimated_input_tokens", 0)
    out.setdefault("estimated_output_tokens", 0)
    out.setdefault("estimated_cost_usd", 0.0)
    return out


def _apply_patches(patches: list[dict], access_level: str | None, run_id: str | None = None, iteration: int | None = None) -> list[dict]:
    out: list[dict] = []
    for patch in patches[:3]:
        file_path = str(patch.get("file_path", "")).strip()
        ast_patch = patch.get("ast_patch")
        unified_diff = str(patch.get("unified_diff", "")).strip()
        new_content = str(patch.get("new_content", ""))
        if not file_path:
            continue
        try:
            if isinstance(ast_patch, dict):
                result = apply_ast_patch(
                    file_path,
                    operation=str(ast_patch.get("operation", "")),
                    target=str(ast_patch.get("target", "")),
                    code=str(ast_patch.get("code", "")),
                    access_level=access_level,
                )
            elif unified_diff:
                result = apply_unified_diff(file_path, unified_diff, access_level=access_level)
            else:
                result = apply_patch(file_path, new_content, access_level=access_level)
            out.append(result)
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
            if run_id is not None:
                _add_cost_event(
                    run_id,
                    "approval_required",
                    "High-risk patch requires approval",
                    {
                        "file": exc.file_path or file_path,
                        "risk_level": exc.risk_level,
                        "reasons": exc.reasons,
                        "stats": exc.stats,
                        "patch_preview": preview[:1000],
                        "patch": patch_payload,
                        "iteration": iteration or 0,
                        **meta,
                    },
                    "coder",
                )
            out.append({"file": file_path, "error": str(exc), "diff": "", "archive": "", "rollback_id": ""})
        except Exception as exc:
            out.append({"file": file_path, "error": str(exc), "diff": "", "archive": "", "rollback_id": ""})
    return out


def _add_cost_event(run_id: str, event_type: str, title: str, payload: dict, role: str) -> None:
    add_event(run_id, event_type, title, payload, agent_role=role)


def _maybe_run_plugin(plan_meta: dict, access_level: str | None) -> dict | None:
    plugin_call = plan_meta.get("plugin_call")
    if not isinstance(plugin_call, dict):
        return None
    name = str(plugin_call.get("name", "")).strip()
    if not name:
        return None
    input_data = plugin_call.get("input_data")
    result = call_plugin(name, input_data if isinstance(input_data, dict) else {}, access_level=access_level)
    return {"name": name, "result": result}


def _augment_context_with_search(base_context: str, query: str, use_files: bool) -> str:
    hits = search_files(query, top_k=5)
    if not hits:
        return base_context
    lines = ["Relevant indexed files:"]
    for item in hits:
        path = str(item.get("path", ""))
        lines.append(f"- {path}")
        if use_files:
            snippet = str(item.get("content", ""))[:400]
            lines.append(f"  snippet: {snippet}")
    joined = "\n".join(lines)
    merged = f"{base_context}\n\n{joined}".strip()
    return merged[:4000]


def run_multi_agent_task(
    task: str,
    access_level: str | None,
    model: str | None,
    max_cost_usd: float | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    run_id = create_run(task=task, model=model, access_level=access_level, profile=profile)
    budget = BudgetCheck(max_cost_usd=max_cost_usd or 0.5)

    _add_cost_event(run_id, "analyze", "Multi-agent task started", {"task": task, "max_cost_usd": budget.max_cost_usd}, "planner")

    try:
        assert_can_run_autonomous(access_level)
    except PermissionError as exc:
        _add_cost_event(run_id, "error", "Access denied", {"error": str(exc)}, "planner")
        finish_run(run_id, "blocked", str(exc))
        run = get_run(run_id)
        return {"ok": False, "run_id": run_id, "error": str(exc), "events": run["events"] if run else []}

    context = _context_snapshot()
    tool_decision = decide_tools(task, context, access_level)
    _add_cost_event(run_id, "tool_decision", "Tool Decision", tool_decision, "planner")
    if tool_decision.get("use_search", False):
        context = _augment_context_with_search(context, task, bool(tool_decision.get("use_files", False)))

    use_plugins = bool(tool_decision.get("use_plugins", False)) and can_run_autonomous(access_level)
    use_tests = can_run_tests(access_level) and (
        bool(tool_decision.get("use_tests", False)) or can_run_autonomous(access_level)
    )
    iterations: list[dict] = []

    for i in range(1, 4):
        iteration: dict[str, Any] = {"iteration": i}

        plan_meta = _normalize_role_output(planner(task, context, model=model), "planner", model)
        if not budget.can_spend(plan_meta["estimated_cost_usd"]):
            _add_cost_event(run_id, "error", "Budget exceeded before planner", plan_meta, "planner")
            finish_run(run_id, "budget_blocked", "Estimated cost budget exceeded")
            run = get_run(run_id)
            return {"ok": False, "run_id": run_id, "iterations": iterations, "events": run["events"] if run else [], "error": "Budget exceeded"}
        budget.spend(plan_meta["estimated_cost_usd"])
        iteration["plan"] = plan_meta["output"]
        _add_cost_event(run_id, "plan", f"Iteration {i}: planner", plan_meta, "planner")
        if use_plugins:
            try:
                plugin_result = _maybe_run_plugin(plan_meta, access_level)
                if plugin_result is not None:
                    iteration["plugin"] = plugin_result
                    _add_cost_event(run_id, "plan", f"Iteration {i}: plugin {plugin_result['name']}", plugin_result, "planner")
            except Exception as exc:
                _add_cost_event(run_id, "error", f"Iteration {i}: plugin failed", {"error": str(exc)}, "planner")

        code_meta = _normalize_role_output(coder(plan_meta["output"], context, model=model), "coder", model)
        code_meta.setdefault("json", {"patches": code_meta.get("patches", []) if isinstance(code_meta.get("patches"), list) else []})
        if not budget.can_spend(code_meta["estimated_cost_usd"]):
            _add_cost_event(run_id, "error", "Budget exceeded before coder", code_meta, "coder")
            finish_run(run_id, "budget_blocked", "Estimated cost budget exceeded")
            run = get_run(run_id)
            return {"ok": False, "run_id": run_id, "iterations": iterations, "events": run["events"] if run else [], "error": "Budget exceeded"}
        budget.spend(code_meta["estimated_cost_usd"])
        _add_cost_event(run_id, "patch", f"Iteration {i}: coder patches", code_meta, "coder")

        patch_results: list[dict] = []
        if can_write_files(access_level):
            patch_results = _apply_patches(code_meta.get("json", {}).get("patches", []), access_level, run_id=run_id, iteration=i)
            for p in patch_results:
                payload = {
                    "diff": p.get("diff", ""),
                    "rollback_id": p.get("rollback_id", ""),
                    "file": p.get("file", ""),
                    "file_status": p.get("file_status", "unknown"),
                    "hunks_count": p.get("hunks_count", 0),
                    "added_lines": p.get("added_lines", 0),
                    "removed_lines": p.get("removed_lines", 0),
                    "risk_level": p.get("risk_level", "unknown"),
                    "approval_required": bool(p.get("approval_required", False)),
                    "files_changed_count": p.get("files_changed_count", 1),
                }
                _add_cost_event(run_id, "diff", f"Iteration {i}: diff {p.get('file', '')}", payload, "coder")
        iteration["patches"] = patch_results

        build_result = {"ok": False, "output": "Build not permitted"}
        test_result = {"ok": False, "output": "Tests not permitted"}
        if use_tests:
            build_result = run_build(access_level=access_level)
            test_result = run_tests(access_level=access_level)
        _add_cost_event(run_id, "build", f"Iteration {i}: build", build_result, "tester")
        _add_cost_event(run_id, "test", f"Iteration {i}: tests", test_result, "tester")

        if use_tests:
            tester_meta = _normalize_role_output(tester(f"Build: {build_result}\nTests: {test_result}", model=model), "tester", model)
            if budget.can_spend(tester_meta["estimated_cost_usd"]):
                budget.spend(tester_meta["estimated_cost_usd"])
            _add_cost_event(run_id, "test", f"Iteration {i}: tester analysis", tester_meta, "tester")

        diff_text = git_diff()
        reviewer_meta = _normalize_role_output(reviewer(diff_text, context, model=model), "reviewer", model)
        if budget.can_spend(reviewer_meta["estimated_cost_usd"]):
            budget.spend(reviewer_meta["estimated_cost_usd"])
        _add_cost_event(run_id, "diff", f"Iteration {i}: reviewer", reviewer_meta, "reviewer")

        iteration["build"] = build_result
        iteration["tests"] = test_result

        if bool(build_result.get("ok")) and bool(test_result.get("ok")):
            iteration["status"] = "done"
            iterations.append(iteration)
            _add_cost_event(run_id, "result", "Multi-agent finished", {"iteration": i, "estimated_total_cost_usd": round(budget.current_cost_usd, 6)}, "reviewer")
            finish_run(run_id, "done", "Build and tests passed")
            run = get_run(run_id)
            return {"ok": True, "run_id": run_id, "iterations": iterations, "events": run["events"] if run else [], "estimated_total_cost_usd": round(budget.current_cost_usd, 6)}

        errors = summarize_errors(str(build_result.get("output", "")), str(test_result.get("output", "")))
        fixer_meta = _normalize_role_output(fixer(errors, context, model=model), "fixer", model)
        fixer_meta.setdefault("json", {"patches": fixer_meta.get("patches", []) if isinstance(fixer_meta.get("patches"), list) else []})
        if budget.can_spend(fixer_meta["estimated_cost_usd"]):
            budget.spend(fixer_meta["estimated_cost_usd"])
        _add_cost_event(run_id, "fix", f"Iteration {i}: fixer", fixer_meta, "fixer")

        if can_write_files(access_level):
            fix_results = _apply_patches(fixer_meta.get("json", {}).get("patches", []), access_level, run_id=run_id, iteration=i)
            iteration.setdefault("patches", []).extend(fix_results)

        iteration["status"] = "needs_fix"
        iteration["error_summary"] = errors
        iterations.append(iteration)

    _add_cost_event(run_id, "result", "Multi-agent reached iteration limit", {"status": "failed", "estimated_total_cost_usd": round(budget.current_cost_usd, 6)}, "fixer")
    finish_run(run_id, "failed", "Max iterations reached")
    run = get_run(run_id)
    return {"ok": False, "run_id": run_id, "iterations": iterations, "events": run["events"] if run else [], "error": "Max iterations reached", "estimated_total_cost_usd": round(budget.current_cost_usd, 6)}

