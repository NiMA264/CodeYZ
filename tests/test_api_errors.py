from fastapi.testclient import TestClient

from packages.server.app import app


def test_api_error_format_for_forbidden_task_auto(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    client = TestClient(app)
    response = client.post(
        "/task/auto",
        headers={"x-api-key": "token123"},
        json={"task": "x", "access_level": "Nur lesen"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["ok"] is False
    assert data["code"] == "autonomous_access_denied"
    assert "message" in data
    assert "hint" in data


def test_api_error_format_for_chat_validation(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    client = TestClient(app)
    response = client.post(
        "/chat",
        headers={"x-api-key": "token123"},
        json={"message": "hello", "model": "invalid-model"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["ok"] is False
    assert data["code"] == "unsupported_model"
    assert "message" in data
    assert "hint" in data


def test_api_error_code_for_plugin_not_found(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    client = TestClient(app)
    response = client.post(
        "/plugins/run",
        headers={"x-api-key": "token123"},
        json={"name": "missing_plugin", "input_data": {}, "access_level": "Nur lesen"},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["ok"] is False
    assert data["code"] == "plugin_not_found"
