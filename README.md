# CodeYZ

CodeYZ is a local coding agent similar to Codex.

## Features

* Autonomous code generation
* Bug fixing loop
* Docker sandbox execution
* Git integration
* VS Code integration
* Safe shell command execution
* Project-local file tools
* Local FastAPI agent server

## Stack

* Python (core)
* FastAPI (server)
* Typer (CLI)
* SQLite (memory)
* Docker (sandbox)
* OpenAI API (intelligence)

## CLI Commands

* `python -m packages.cli.main ask-cmd "<task>"`
* `python -m packages.cli.main test`
* `python -m packages.cli.main diff`
* `python -m packages.cli.main status`
* `python -m packages.cli.main run-task-cmd "<task>"`
* `python -m packages.cli.main server`

## Server (Phase 3)

Start server:

* `python -m packages.cli.main server`
* Base URL: `http://127.0.0.1:8765`

Endpoints:

* `GET /health`
* `POST /chat`
* `POST /task`
* `GET /git/status`
* `GET /git/diff`
* `GET /projects`
* `POST /projects`
* `GET /plugins`
* `GET /automations`
* `POST /automations`

Auth:

* If `CODEYZ_LOCAL_TOKEN` is set, send it via `x-api-key` or `Authorization: Bearer <token>`.
* If `CODEYZ_LOCAL_TOKEN` is not set, only localhost access is allowed.

## Safety Rules

* No auto-commit
* No auto-push
* No passwords stored
* OpenAI API key only via environment variable or local secret file (not committed)
* No file access outside explicitly allowed project paths
* No browser automation login for ChatGPT
* No external connections except OpenAI API

## Integration Roadmap

ChatGPT integration comes later via Apps SDK, GPT Action, or MCP.

## Goal

Create a cost-efficient, token-optimized coding agent.

## VS Code Extension (Phase 5)

CodeYZ includes a local VS Code sidebar extension in `vscode-extension/`.

Setup:

1. `cd vscode-extension`
2. `npm install`
3. `npm run compile`
4. Open `vscode-extension` in VS Code
5. Press `F5` to launch Extension Development Host

Notes:

* CodeYZ server must run separately at `http://127.0.0.1:8765`.
* Configure `codeyz.serverUrl` and optional `codeyz.localToken` in VS Code settings.
* The extension sends token only as `x-api-key` header.
* No OpenAI key is stored in the extension.
