# Release Runbook (Local Beta)

## Pre-release checklist

1. `ruff check .`
2. `pytest -q`
3. `python scripts/release_check.py`
4. Confirm `VERSION` updated.
5. Confirm `CHANGELOG.md` updated.
6. Validate installer/zip artifacts are not tracked unintentionally.

## Build artifacts

```bash
python scripts/build_exe.py
python scripts/release_zip.py
```

## Packaging smoke

- `codeyz --help`
- `codeyz setup`
- `GET /health` returns `version`

## CI

- CI includes release readiness checks and packaging smoke tests.
