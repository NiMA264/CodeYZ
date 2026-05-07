from __future__ import annotations

from packages.core.settings import DEFAULT_MODEL, get_default_model


def test_model_precedence_codeyz_model_over_model(monkeypatch) -> None:
    monkeypatch.setenv("MODEL", "gpt-5.4")
    monkeypatch.setenv("CODEYZ_MODEL", "gpt-5.5")
    assert get_default_model() == "gpt-5.5"


def test_model_fallback_to_legacy_model(monkeypatch) -> None:
    monkeypatch.delenv("CODEYZ_MODEL", raising=False)
    monkeypatch.setenv("MODEL", "gpt-5.4")
    assert get_default_model() == "gpt-5.4"


def test_model_default_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("CODEYZ_MODEL", raising=False)
    monkeypatch.delenv("MODEL", raising=False)
    assert get_default_model() == DEFAULT_MODEL
