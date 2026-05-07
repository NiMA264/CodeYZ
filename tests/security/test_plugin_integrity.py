from __future__ import annotations

import hashlib
import json
from pathlib import Path

from packages.core.plugins.plugin_loader import TRUSTED_HASHES_ENV, load_plugins


def _write_plugin(root: Path, name: str = "trusted_plugin") -> Path:
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": name,
                "description": "test plugin",
                "version": "1.0.0",
                "permissions": ["read_files"],
                "entry": "plugin.py",
                "functions": ["run"],
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(
        "def run(input_data):\n    return {'ok': True, 'name': input_data.get('name', '')}\n",
        encoding="utf-8",
    )
    return plugin_dir


def _plugin_hash(plugin_dir: Path) -> str:
    digest = hashlib.sha256()
    digest.update((plugin_dir / "manifest.json").read_bytes())
    digest.update((plugin_dir / "plugin.py").read_bytes())
    digest.update(plugin_dir.name.encode("utf-8"))
    return digest.hexdigest()


def test_plugin_missing_hash_rejected(tmp_path: Path, monkeypatch) -> None:
    _write_plugin(tmp_path, "plugin_missing_hash")
    trusted_file = tmp_path / "trusted_plugins.json"
    trusted_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(TRUSTED_HASHES_ENV, str(trusted_file))

    loaded = load_plugins(tmp_path)
    assert loaded == []


def test_plugin_hash_mismatch_rejected(tmp_path: Path, monkeypatch) -> None:
    plugin_dir = _write_plugin(tmp_path, "plugin_mismatch")
    trusted_file = tmp_path / "trusted_plugins.json"
    trusted_file.write_text(json.dumps({"plugin_mismatch": "deadbeef"}), encoding="utf-8")
    monkeypatch.setenv(TRUSTED_HASHES_ENV, str(trusted_file))

    loaded = load_plugins(tmp_path)
    assert loaded == []
    assert _plugin_hash(plugin_dir) != "deadbeef"


def test_valid_plugin_hash_loaded(tmp_path: Path, monkeypatch) -> None:
    plugin_dir = _write_plugin(tmp_path, "plugin_valid")
    trusted_file = tmp_path / "trusted_plugins.json"
    trusted_file.write_text(json.dumps({"plugin_valid": _plugin_hash(plugin_dir)}), encoding="utf-8")
    monkeypatch.setenv(TRUSTED_HASHES_ENV, str(trusted_file))

    loaded = load_plugins(tmp_path)
    assert any(item["name"] == "plugin_valid" for item in loaded)
