import os

from dotenv import load_dotenv
from openai import OpenAI

from packages.core.runtime_paths import get_env_file_path

load_dotenv()
load_dotenv(dotenv_path=get_env_file_path(), override=False)

DEFAULT_MODEL = os.getenv("MODEL", "gpt-5.4-mini")
ALLOWED_MODELS = {"gpt-5.4-mini", "gpt-5.4", "gpt-5.5"}

BASE_SYSTEM = """
You are CodeYZ, a local coding agent.
Be concise. Use minimal tokens.
Only request relevant files.
Prefer diffs over full files.
Never reveal secrets.
""".strip()


MODE_HINTS = {
    "Chat": "General chat mode. Explain clearly.",
    "Code": "Focus on concrete code suggestions and small patches.",
    "Review": "Focus on risks, bugs, and test gaps.",
    "Fix": "Focus on root-cause fixes with minimal changes.",
    "Projekt planen": "Focus on implementation plan and milestones.",
}

ACCESS_HINTS = {
    "Nur lesen": "Do not propose executing changes. Explain only.",
    "Dateien ändern": "Suggest file changes, but do not assume execution.",
    "Tests ausführen": "You may suggest running tests/build commands.",
    "Autonom": "You may recommend autonomous task loop via /task/auto.",
    "Gefährlich deaktiviert": "Never suggest destructive commands.",
}


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask(
    task: str,
    context: str = "",
    model: str | None = None,
    mode: str | None = None,
    access_level: str | None = None,
    plan_mode: bool = False,
) -> str:
    selected_model = model if model in ALLOWED_MODELS else DEFAULT_MODEL

    system_parts = [BASE_SYSTEM]
    if mode and mode in MODE_HINTS:
        system_parts.append(f"Mode: {MODE_HINTS[mode]}")
    if access_level and access_level in ACCESS_HINTS:
        system_parts.append(f"Access: {ACCESS_HINTS[access_level]}")
    if plan_mode:
        system_parts.append("Plan mode is enabled: return only a short actionable plan. No execution steps.")

    system_text = "\n".join(system_parts)

    messages = [{"role": "system", "content": system_text}, {"role": "user", "content": f"Task:\n{task}"}]
    if context.strip():
        messages.append({"role": "user", "content": f"Context:\n{context}"})

    response = _client().responses.create(model=selected_model, input=messages)
    return response.output_text
