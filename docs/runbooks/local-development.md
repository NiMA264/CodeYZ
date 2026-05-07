# Local Development Runbook

## Prerequisites

- Python 3.11+
- Git
- Optional: Playwright for browser UI smoke checks

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[dev]
```

## Daily checks

```bash
ruff check .
pytest -q
python scripts/release_check.py
```

## Start server

```bash
codeyz server
```

Open `http://127.0.0.1:8765/ui/`.

## Runtime notes

- Runtime root can be overridden via `CODEYZ_RUNTIME_ROOT`.
- Model precedence: `CODEYZ_MODEL` -> `MODEL` -> `gpt-5.4-mini`.
