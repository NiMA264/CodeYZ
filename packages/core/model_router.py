from __future__ import annotations

ALLOWED_MODELS = {"gpt-5.4-mini", "gpt-5.4", "gpt-5.5"}

DEFAULT_ROLE_MODELS = {
    "planner": "gpt-5.5",
    "coder": "gpt-5.4",
    "tester": "gpt-5.4-mini",
    "reviewer": "gpt-5.5",
    "fixer": "gpt-5.4",
}

_ROLE_MODELS = dict(DEFAULT_ROLE_MODELS)


def validate_model(model: str) -> str:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"Unsupported model: {model}")
    return model


def get_model_for_role(role: str, fallback_model: str | None = None) -> str:
    if role in _ROLE_MODELS:
        return _ROLE_MODELS[role]
    if fallback_model:
        return validate_model(fallback_model)
    return "gpt-5.4-mini"


def set_model_for_role(role: str, model: str) -> str:
    validated = validate_model(model)
    _ROLE_MODELS[role] = validated
    return validated


def set_role_models(mapping: dict[str, str]) -> dict[str, str]:
    for role, model in mapping.items():
        set_model_for_role(role, model)
    return dict(_ROLE_MODELS)
