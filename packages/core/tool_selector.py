from __future__ import annotations

import json
import os

from packages.core.agent import _client
from packages.core.permissions import can_run_autonomous, can_run_tests

DEFAULT_DECISION = {
    "use_search": True,
    "use_plugins": False,
    "use_tests": True,
    "use_files": True,
    "reasoning": "Default decision: use search/files and tests, keep plugins off unless clearly needed.",
}


def _coerce_decision(raw: dict) -> dict:
    out = {
        "use_search": bool(raw.get("use_search", DEFAULT_DECISION["use_search"])),
        "use_plugins": bool(raw.get("use_plugins", DEFAULT_DECISION["use_plugins"])),
        "use_tests": bool(raw.get("use_tests", DEFAULT_DECISION["use_tests"])),
        "use_files": bool(raw.get("use_files", DEFAULT_DECISION["use_files"])),
        "reasoning": str(raw.get("reasoning", DEFAULT_DECISION["reasoning"]))[:240],
    }
    return out


def _apply_permission_rules(decision: dict, access_level: str | None) -> dict:
    out = dict(decision)
    notes: list[str] = []
    if out["use_tests"] and not can_run_tests(access_level):
        out["use_tests"] = False
        notes.append("tests disabled by permissions")
    if out["use_plugins"] and not can_run_autonomous(access_level):
        out["use_plugins"] = False
        notes.append("plugins disabled by permissions")
    if notes:
        out["reasoning"] = f"{out['reasoning']} ({', '.join(notes)})".strip()
    return out


def decide_tools(task: str, context: str, access_level: str | None) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        return _apply_permission_rules(dict(DEFAULT_DECISION), access_level)

    clipped_context = context[:1200]
    prompt = (
        "Du entscheidest nur Tools, keine Umsetzung.\n"
        "Antworte als kompaktes JSON mit Feldern: "
        "use_search, use_plugins, use_tests, use_files, reasoning.\n"
        f"Task: {task}\nContext:\n{clipped_context}"
    )
    try:
        response = _client().responses.create(
            model="gpt-5.4-mini",
            input=[
                {"role": "system", "content": "Decide tools only. Return JSON only."},
                {"role": "user", "content": prompt},
            ],
        )
        parsed = json.loads(response.output_text)
        decision = _coerce_decision(parsed)
    except Exception:
        decision = dict(DEFAULT_DECISION)
    return _apply_permission_rules(decision, access_level)
