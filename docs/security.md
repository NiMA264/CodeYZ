# CodeYZ Security Hardening

## Workspace Path Boundaries

- Security boundaries use canonical path checks with `Path.resolve()` + `Path.is_relative_to()`.
- Shared helper: `packages/core/path_security.py`.
- Prefix-string checks are not used for security boundaries.

## Shell Execution

- Shell commands run with `shell=False`.
- Allowed executables: `pytest`, `ruff`, `python`, `git`.
- Blocked shell chaining/injection tokens: `;`, `&&`, `||`, `|`, `>`, `<`.
- Blocked shell interpreters: `cmd`, `powershell`, `bash -c`, `sh -c`.
- Output is truncated and command timeout is enforced.

## Plugin Integrity

- Plugin loader can enforce trusted plugin hashes via SHA256.
- Configure hash file via `CODEYZ_TRUSTED_PLUGIN_HASHES_FILE`.
- If trusted hashes are configured:
  - plugin missing hash entry -> rejected
  - hash mismatch -> rejected
  - hash match -> loaded
- When trusted hashes are configured, plugins default to subprocess execution mode (`shell=False`) with timeout and JSON-only I/O validation.

## Runtime Isolation in Tests

- `tests/conftest.py` sets `CODEYZ_RUNTIME_ROOT` to a repository-local folder.
- Tests do not write runtime files into real user profile directories.

## Request Correlation and Safe Logging

- FastAPI middleware assigns a per-request `request_id` and returns it in `x-request-id`.
- API error payloads include `request_id` when available.
- Structured logging uses JSON-compatible records with `component`, `request_id`, and `run_id`.
- Secret-like values are redacted before log output.
