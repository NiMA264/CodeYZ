import json
import os
from typing import Any

from openai import OpenAI

from packages.core.executor import run_build, run_tests, summarize_errors
from packages.core.patcher import apply_patch
from packages.tools.files import list_files, read_file

MODEL = os.getenv("CODEYZ_MODEL", "gpt-5.4-mini")
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
    return json.loads(raw[start:end + 1])


def _plan_and_patch(task: str, error_context: str = "") -> dict[str, Any]:
    snapshot = _project_snapshot()
    prompt = f"""
Task: {task}

Error context:
{error_context or 'none'}

Project snapshot:
{snapshot}

Return JSON with keys:
- plan: short string
- patches: array of objects {{"file_path": "...", "new_content": "..."}}
Limit patches to at most 3 files.
"""
    response = _client().responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return _extract_json(response.output_text)


def run_autonomous_task(task: str) -> dict[str, Any]:
    logs: list[dict[str, Any]] = []
    last_error = ""

    for iteration in range(1, 6):
        step: dict[str, Any] = {"iteration": iteration}
        plan_payload = _plan_and_patch(task, last_error)
        step["plan"] = plan_payload.get("plan", "")

        patch_results: list[dict[str, str]] = []
        for patch in plan_payload.get("patches", [])[:3]:
            file_path = str(patch.get("file_path", "")).strip()
            new_content = str(patch.get("new_content", ""))
            if not file_path:
                continue
            try:
                patch_results.append(apply_patch(file_path, new_content))
            except Exception as exc:
                patch_results.append({"file": file_path, "diff": "", "archive": "", "error": str(exc)})

        step["patches"] = patch_results

        build_result = run_build()
        test_result = run_tests()
        step["build"] = build_result
        step["tests"] = test_result

        if bool(build_result.get("ok")) and bool(test_result.get("ok")):
            step["status"] = "done"
            logs.append(step)
            return {"ok": True, "iterations": logs}

        step["status"] = "needs_fix"
        last_error = summarize_errors(str(build_result.get("output", "")), str(test_result.get("output", "")))
        step["error_summary"] = last_error
        logs.append(step)

    return {"ok": False, "iterations": logs, "error": "Max iterations reached"}
