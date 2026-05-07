# CodeYZ Architecture Notes

## Security-Critical Building Blocks

- Path boundary validation: `packages/core/path_security.py`
- Workspace/project model: `packages/core/project_paths.py`
- Shell execution safety: `packages/tools/shell.py`
- Plugin loading and permissions: `packages/core/plugins/plugin_loader.py`, `packages/core/plugins/plugin_permissions.py`
- Runtime persistence roots: `packages/core/runtime_paths.py`
- Task run orchestration package: `packages/core/task_runs/` (`lifecycle`, `storage`, `events`, `metrics`, `resume`, `replay`)
- Central settings/env resolution: `packages/core/settings.py`
- Structured logging helpers: `packages/core/logging_utils.py`

## Runtime Flow

1. UI/CLI calls FastAPI routes.
2. Routes delegate into core orchestration (`agent_loop`, `agent_pipeline`).
3. File/shell/plugin actions are guarded by access-level checks and path/security helpers.
4. Events, checkpoints, and run metrics are persisted in runtime storage.
5. FastAPI middleware attaches `request_id` and propagates it into API error payloads and autonomous task run metadata.
