from packages.core import tool_selector


class _DummyResponse:
    def __init__(self, text: str):
        self.output_text = text


class _DummyClient:
    class responses:
        @staticmethod
        def create(**_kwargs):
            return _DummyResponse('{"use_search": true, "use_plugins": true, "use_tests": true, "use_files": true, "reasoning": "needed"}')


def test_decision_json_valid(monkeypatch) -> None:
    monkeypatch.setattr(tool_selector, "_client", lambda: _DummyClient())
    out = tool_selector.decide_tools("task", "ctx", "Autonom")
    assert isinstance(out, dict)
    assert set(out.keys()) == {"use_search", "use_plugins", "use_tests", "use_files", "reasoning"}


def test_permissions_block_tools(monkeypatch) -> None:
    monkeypatch.setattr(tool_selector, "_client", lambda: _DummyClient())
    out = tool_selector.decide_tools("task", "ctx", "Nur lesen")
    assert out["use_search"] is True
    assert out["use_files"] is True
    assert out["use_tests"] is False
    assert out["use_plugins"] is False


def test_reasoning_present(monkeypatch) -> None:
    monkeypatch.setattr(tool_selector, "_client", lambda: _DummyClient())
    out = tool_selector.decide_tools("task", "ctx", "Autonom")
    assert isinstance(out["reasoning"], str)
    assert len(out["reasoning"]) > 0
