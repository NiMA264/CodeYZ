import json
from openai import OpenAI

from packages.core.costs import estimate_cost
from packages.core.settings import get_default_model, get_openai_api_key
from packages.core.model_router import get_model_for_role

DEFAULT_MODEL = get_default_model()


def _client() -> OpenAI:
    return OpenAI(api_key=get_openai_api_key())


def _run(role: str, system_prompt: str, user_prompt: str, fallback_model: str | None = None) -> dict:
    model = get_model_for_role(role, fallback_model=fallback_model or DEFAULT_MODEL)
    response = _client().responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    output = response.output_text
    cost_meta = estimate_cost(model, user_prompt, output)
    return {
        "role": role,
        "model": model,
        "output": output,
        **cost_meta,
    }


def planner(task: str, context: str, model: str | None = None) -> dict:
    system = "You are Planner. Return only a concise implementation plan. No code."
    return _run("planner", system, f"Task:\n{task}\n\nContext:\n{context}", fallback_model=model)


def coder(plan: str, context: str, model: str | None = None) -> dict:
    system = "You are Coder. Return JSON only with patches [{file_path,unified_diff}] and fallback [{file_path,new_content}] if needed."
    raw = _run("coder", system, f"Plan:\n{plan}\n\nContext:\n{context}", fallback_model=model)
    raw["json"] = _extract_json(raw["output"])
    return raw


def tester(context: str, model: str | None = None) -> dict:
    system = "You are Tester. Analyze test/build outcomes only."
    return _run("tester", system, f"Context:\n{context}", fallback_model=model)


def reviewer(diff: str, context: str, model: str | None = None) -> dict:
    system = "You are Reviewer. Evaluate diff quality and risks only."
    return _run("reviewer", system, f"Diff:\n{diff}\n\nContext:\n{context}", fallback_model=model)


def fixer(errors: str, context: str, model: str | None = None) -> dict:
    system = "You are Fixer. Return JSON only with patches [{file_path,unified_diff}] and fallback [{file_path,new_content}] if needed."
    raw = _run("fixer", system, f"Errors:\n{errors}\n\nContext:\n{context}", fallback_model=model)
    raw["json"] = _extract_json(raw["output"])
    return raw


def _extract_json(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {"patches": []}
    try:
        return json.loads(raw[start : end + 1])
    except Exception:
        return {"patches": []}
