import os

from openai import OpenAI

from packages.tools.files import list_files
from packages.tools.git import git_diff, git_status
from packages.tools.shell import run_shell

MODEL = os.getenv("CODEYZ_MODEL", "gpt-5.4-mini")

SYSTEM = """
You are CodeYZ, a local coding agent.

Rules:
- Be concise.
- Minimize token usage.
- Never request secrets.
- Never ask for full repositories.
- Prefer small patches.
- Do not commit, push, deploy, or delete without approval.
- Only suggest safe commands.
"""


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _summarize_files() -> str:
    files = list_files(".")
    important = [
        f for f in files
        if f.endswith((".py", ".md", ".toml", ".json", ".yml", ".yaml"))
    ]
    return "\n".join(important[:120])


def _detect_test_command(files: str) -> str | None:
    if "pyproject.toml" in files:
        return "py -3.11 -m pytest"
    if "package.json" in files:
        return "npm test"
    return None


def plan_task(task: str) -> str:
    files = _summarize_files()
    prompt = f"""
Task:
{task}

Project files:
{files}

Return:
1. Short plan
2. Files likely needed
3. Safe commands to run
4. Risks
"""

    response = _client().responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return response.output_text


def run_task(task: str) -> str:
    files = _summarize_files()
    plan = plan_task(task)

    test_command = _detect_test_command(files)
    test_output = ""

    if test_command:
        try:
            test_output = run_shell(test_command)
        except Exception as exc:
            test_output = f"Test command failed: {exc}"

    diff = git_diff()
    status = git_status()

    return f"""
CODEYZ PLAN
===========
{plan}

TEST OUTPUT
===========
{test_output or "No test command detected."}

GIT STATUS
==========
{status or "clean"}

GIT DIFF
========
{diff or "No changes."}
""".strip()
