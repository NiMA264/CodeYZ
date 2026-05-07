from pathlib import Path

from fastapi.testclient import TestClient

from packages.core.plugins.plugin_loader import load_plugins
from packages.core.plugins.plugin_permissions import enforce_plugin_permissions
from packages.core.plugins.plugin_registry import (
    call_plugin,
    disable_plugin,
    enable_plugin,
    get_plugin,
)
from packages.server.app import app


def test_plugin_load_and_execute() -> None:
    root = Path(__file__).resolve().parents[1] / "plugins"
    load_plugins(root)
    plugin = get_plugin("example_plugin")
    assert plugin is not None
    out = call_plugin("example_plugin", {"name": "test"}, access_level="Nur lesen")
    assert out["result"] == "ok:test"


def test_invalid_manifest_blocked(tmp_path: Path) -> None:
    p = tmp_path / "bad_plugin"
    p.mkdir(parents=True)
    (p / "manifest.json").write_text('{"name":"bad"}', encoding="utf-8")
    (p / "plugin.py").write_text("def run(input_data):\n    return {'ok': True}\n", encoding="utf-8")

    loaded = load_plugins(tmp_path)
    assert loaded == []


def test_permission_violation_blocked() -> None:
    try:
        enforce_plugin_permissions(["write_files"], "Nur lesen")
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected PermissionError")


def test_enable_disable() -> None:
    root = Path(__file__).resolve().parents[1] / "plugins"
    load_plugins(root)
    disable_plugin("example_plugin")
    plugin = get_plugin("example_plugin")
    assert plugin is not None and plugin["enabled"] is False
    enable_plugin("example_plugin")
    plugin = get_plugin("example_plugin")
    assert plugin is not None and plugin["enabled"] is True


def test_plugin_api_run(monkeypatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    client = TestClient(app)
    res = client.post(
        "/plugins/run",
        headers={"x-api-key": "token123"},
        json={"name": "example_plugin", "input_data": {"name": "api"}, "access_level": "Nur lesen"},
    )
    assert res.status_code == 200
    assert res.json()["result"]["result"] == "ok:api"


def test_plugins_endpoint_returns_useful_error_for_malformed_hash_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    bad = tmp_path / "bad_hashes.json"
    bad.write_text("[not-an-object]", encoding="utf-8")
    monkeypatch.setenv("CODEYZ_TRUSTED_PLUGIN_HASHES_FILE", str(bad))
    client = TestClient(app)
    res = client.get("/plugins", headers={"x-api-key": "token123"})
    assert res.status_code == 400
    payload = res.json()
    assert payload["code"] == "plugin_config_invalid"
    assert "trusted plugin hash config" in payload["hint"].lower() or "hash" in payload["hint"].lower()
