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

## Developer Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[dev]
```

Quality and tests:

```bash
ruff check .
pytest -q
```

Optional Playwright browser install for full UI smoke coverage:

```bash
python -m playwright install chromium
pytest -q tests/test_ui_smoke.py
```

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

## Beta Install (Local)

```bash
git clone <repo-url>
cd CodeYZ
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[dev]
python scripts/release_check.py
codeyz setup
codeyz server
```

For trusted plugin mode, set `CODEYZ_TRUSTED_PLUGIN_HASHES_FILE` to a JSON file:

```json
{
  "example_plugin": "0123456789abcdef..."
}
```

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

Model/config defaults:

- Default model resolution is centralized in `packages/core/settings.py`
- Precedence: `CODEYZ_MODEL` -> legacy `MODEL` -> `gpt-5.4-mini`

## Features

- CLI + setup diagnostics
- FastAPI server with auth and safe routes
- Web UI with explorer, timeline, rollback, plugins, search, system status
- Workspace indexing + relevance search
- Context pinning and selected-file context
- Autonomous run timeline with tool decisions
- Safe shell + permission model
- Request correlation id (`x-request-id`) in API responses and error payloads
- Background autonomous job queue for non-blocking `/task/auto` execution
- Cooperative cancellation endpoint for queued/running autonomous jobs (`POST /task/cancel/{run_id}`)

## Security Model

- Server is source of truth for permissions
- Access levels: `Nur lesen`, `Dateien ändern`, `Tests ausführen`, `Autonom`
- Blocked paths: `.env`, `.venv`, `.git`, `node_modules`, outside workspace
- No auto-commit/push/deploy
- OpenAI key only via env/local secret
- Path boundaries are validated with canonical `Path.resolve()` checks (no prefix-based boundary checks)
- Shell execution runs with `shell=False`, command allowlist (`pytest`, `ruff`, `python`, `git`), and injection-token blocking
- Optional plugin integrity enforcement via SHA256 allowlist (`CODEYZ_TRUSTED_PLUGIN_HASHES_FILE`)

## Fehlerbehandlung

- Missing API key: set `OPENAI_API_KEY` or use first-run prompt
- Server unreachable: start with `codeyz server`
- Plugin error: check plugin panel, disable/enable plugin
- Budget exceeded: raise budget or split task
- API error codes: see `docs/api-error-codes.md`

## Test Runtime Isolation

- Tests force `CODEYZ_RUNTIME_ROOT` to a workspace-local directory (`tests/conftest.py`), so no runtime state is written to user profile directories.

## UI Smoke-Test

- Minimaler UI-Smoke-Test ist in `tests/test_ui_smoke.py`.
- Enthält:
  - `/ui/` erreichbar und HTML-Module-Wiring korrekt
  - zentrale UI-Elemente vorhanden (`chat-form`, `messages`, `explorer`, `runs-list`, `plugins-list`)
  - optionaler echter Browser-Init-Check mit Playwright (wird automatisch übersprungen, wenn Playwright nicht installiert ist)
- CI läuft standardmäßig ohne Browser-Binaries; ein separater optionaler Browser-Job kann manuell per `workflow_dispatch` gestartet werden.

## Web UI Features

- Workflow-Karte mit Run-Summary (Task, Patch, Tests, Risk, Decision)
- Focus Modes: `Workflow`, `Code`, `Chat`
- Command Palette: `Ctrl+K`
- Keyboard Shortcuts:
  - `Ctrl+1` / `Ctrl+2` / `Ctrl+3` für Focus Modes
  - `Ctrl+B` Sidebar ein-/ausblenden
  - `Ctrl+E` Explorer ein-/ausblenden
  - `Ctrl+Z` Undo, `Ctrl+Shift+Z` Redo
- Layout:
  - Panels sind einklappbar (collapsible)
  - Sidebars sind resizable (Drag + persistente Breite)
  - UI-Preferences werden zentral persistiert (`codeyz_ui_preferences`)
  - Layout kann exportiert/importiert werden
  - Session Restore stellt letzten UI-Zustand wieder her
- Timeline:
  - Event-Gruppierung mit Expand/Collapse für Details
  - Virtual Scrolling für große Run-Listen
- Details: siehe `docs/ui.md`

## Version

Current version is stored in `VERSION` and exposed in `/health` and UI.
