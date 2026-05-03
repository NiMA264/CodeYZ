import packages.cli.main as cli_main


def test_server_command_uses_direct_app_import(monkeypatch) -> None:
    captured = {}

    def fake_run(target, host=None, port=None):
        captured["target"] = target
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(cli_main.uvicorn, "run", fake_run)
    cli_main.server(open_browser=False)

    assert not isinstance(captured["target"], str)
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
