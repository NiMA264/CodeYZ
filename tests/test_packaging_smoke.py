from __future__ import annotations

from typer.testing import CliRunner
from fastapi.testclient import TestClient

from packages.cli.main import app
from packages.server.app import app as server_app


def test_cli_help_works() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CodeYZ" in result.output


def test_cli_setup_works() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 0
    assert "Environment" in result.output


def test_health_exposes_version() -> None:
    client = TestClient(server_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert "version" in res.json()
