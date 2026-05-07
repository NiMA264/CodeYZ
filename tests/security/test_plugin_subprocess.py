from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from packages.core.plugins.plugin_loader import TRUSTED_HASHES_ENV, load_plugins
from packages.core.plugins.plugin_registry import call_plugin


def _write_plugin(tmp_path: Path, name: str, code: str) -> Path:
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": name,
                "description": "plugin",
                "version": "1.0.0",
                "permissions": ["read_files"],
                "entry": "plugin.py",
                "functions": ["run"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(code, encoding="utf-8")
    return plugin_dir


def _hash(plugin_dir: Path) -> str:
    digest = hashlib.sha256()
    digest.update((plugin_dir / "manifest.json").read_bytes())
    digest.update((plugin_dir / "plugin.py").read_bytes())
    digest.update(plugin_dir.name.encode("utf-8"))
    return digest.hexdigest()


def test_plugin_subprocess_success(monkeypatch, tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path, "sub_ok", "def run(input_data):\n    return {'ok': input_data.get('x')}\n")
    trusted = tmp_path / "trusted_plugins.json"
    trusted.write_text(json.dumps({"sub_ok": _hash(plugin_dir)}), encoding="utf-8")
    monkeypatch.setenv(TRUSTED_HASHES_ENV, str(trusted))
    load_plugins(tmp_path)
    out = call_plugin("sub_ok", {"x": 7}, access_level="Nur lesen")
    assert out["ok"] == 7


def test_plugin_subprocess_invalid_output_rejected(monkeypatch, tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path, "sub_bad", "def run(input_data):\n    return set([1,2,3])\n")
    trusted = tmp_path / "trusted_plugins.json"
    trusted.write_text(json.dumps({"sub_bad": _hash(plugin_dir)}), encoding="utf-8")
    monkeypatch.setenv(TRUSTED_HASHES_ENV, str(trusted))
    load_plugins(tmp_path)
    with pytest.raises(ValueError):
        call_plugin("sub_bad", {}, access_level="Nur lesen")


def test_plugin_subprocess_timeout(monkeypatch, tmp_path: Path) -> None:
    plugin_dir = _write_plugin(tmp_path, "sub_slow", "def run(input_data):\n    import time\n    time.sleep(6)\n    return {'ok': True}\n")
    trusted = tmp_path / "trusted_plugins.json"
    trusted.write_text(json.dumps({"sub_slow": _hash(plugin_dir)}), encoding="utf-8")
    monkeypatch.setenv(TRUSTED_HASHES_ENV, str(trusted))
    load_plugins(tmp_path)
    with pytest.raises(TimeoutError):
        call_plugin("sub_slow", {}, access_level="Nur lesen")
