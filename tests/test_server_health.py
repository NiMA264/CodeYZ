from fastapi.testclient import TestClient

from packages.server.app import app


def test_health_endpoint_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "openai" in data
    assert "index" in data
    assert "plugins" in data
    assert "workspace" in data
    assert "version" in data
