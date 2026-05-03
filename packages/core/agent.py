import os
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv()

MODEL = os.getenv("MODEL", "gpt-5.4-mini")

SYSTEM = """
You are CodeYZ, a local coding agent.
Be concise. Use minimal tokens.
Only request relevant files.
Prefer diffs over full files.
"""


def _client() -> OpenAI:
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask(task, context=""):
    response = _client().responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{task}\n\nContext:\n{context}"},
        ],
    )
    return response.output_text
