# Troubleshooting Runbook

## Missing API key

Symptom:
- Chat/task model calls fail or `/health` shows `openai=failed`.

Fix:
- Set `OPENAI_API_KEY` in environment or `%APPDATA%\CodeYZ\.env`.

## Runtime root not writable

Symptom:
- Setup shows `Runtime root schreibbar` as failed.

Fix:
- Set writable `CODEYZ_RUNTIME_ROOT` path and retry.

## Plugin trust/hash config malformed

Symptom:
- Plugin list endpoint returns `plugin_config_invalid`.

Fix:
- Validate JSON file referenced by `CODEYZ_TRUSTED_PLUGIN_HASHES_FILE`.
- Ensure mapping format: `{ "plugin_name": "sha256hex" }`.

## Port 8765 already in use

Symptom:
- `codeyz server` fails to start.

Fix:
- Stop conflicting process or free the port, then restart.

## Release readiness failures

Symptom:
- `python scripts/release_check.py` fails.

Fix:
- Read failing checklist item and resolve before release.
