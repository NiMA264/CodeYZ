# CodeYZ

CodeYZ is a local coding agent with CLI, API server, Web UI, and VS Code integration.

## Quickstart (Source)

```bash
git clone <repo-url>
cd CodeYZ
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
codeyz setup
codeyz server
```

Open: `http://127.0.0.1:8765/ui/`

## Download & Install (Windows)

### EXE build locally

```bash
python scripts/build_exe.py
```

Result: `dist/codeyz.exe`

### Installer (NSIS)

- Script: `installer/codeyz_installer.nsi`
- Installs to: `C:\Program Files\CodeYZ`
- Creates Desktop and Start Menu shortcuts.

### First run

```bash
codeyz.exe server --open-browser
```

If no API key is configured, CodeYZ prompts once and stores it in:

`%APPDATA%\CodeYZ\.env`

## Commands

- `codeyz setup` - environment checks
- `codeyz server [--open-browser]` - start local API/UI server
- `codeyz chat "..."` - quick model chat
- `codeyz task "..."` - run task loop summary
- `codeyz status` - git status
- `codeyz diff` - git diff
- `codeyz test` - run pytest

## Runtime Data

User config and runtime files are stored in:

`%APPDATA%\CodeYZ\`

- `.env`
- `logs/`
- `runs/`
- `snapshots/`
- `diffs/`
- `sessions.json`
- `automations.json`

## Features

- CLI + setup diagnostics
- FastAPI server with auth and safe routes
- Web UI with explorer, timeline, rollback, plugins, search, system status
- Workspace indexing + relevance search
- Context pinning and selected-file context
- Autonomous run timeline with tool decisions
- Safe shell + permission model

## Security Model

- Server is source of truth for permissions
- Access levels: `Nur lesen`, `Dateien ändern`, `Tests ausführen`, `Autonom`
- Blocked paths: `.env`, `.venv`, `.git`, `node_modules`, outside workspace
- No auto-commit/push/deploy
- OpenAI key only via env/local secret

## Fehlerbehandlung

- Missing API key: set `OPENAI_API_KEY` or use first-run prompt
- Server unreachable: start with `codeyz server`
- Plugin error: check plugin panel, disable/enable plugin
- Budget exceeded: raise budget or split task
- API error codes: see `docs/api-error-codes.md`

## UI Smoke-Test

- Minimaler UI-Smoke-Test ist in `tests/test_ui_smoke.py`.
- Enthält:
  - `/ui/` erreichbar und HTML-Module-Wiring korrekt
  - zentrale UI-Elemente vorhanden (`chat-form`, `messages`, `explorer`, `runs-list`, `plugins-list`)
  - optionaler echter Browser-Init-Check mit Playwright (wird automatisch übersprungen, wenn Playwright nicht installiert ist)

## Version

Current version is stored in `VERSION` and exposed in `/health` and UI.
