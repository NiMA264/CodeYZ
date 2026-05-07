from __future__ import annotations

import os

DEFAULT_MODEL = "gpt-5.4-mini"
ALLOWED_MODELS = {"gpt-5.4-mini", "gpt-5.4", "gpt-5.5"}


def get_default_model() -> str:
    # Backward compatible fallback:
    # prefer CODEYZ_MODEL, fallback to legacy MODEL, then hard default.
    return os.getenv("CODEYZ_MODEL") or os.getenv("MODEL") or DEFAULT_MODEL


def get_openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")
