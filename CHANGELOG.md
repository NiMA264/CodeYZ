# Changelog

## [0.1.0-beta] - 2026-05-07

### Sprint 1 - Security hardening

- Centralized canonical path-boundary validation.
- Hardened shell execution (`shell=False`, allowlist, injection token blocking).
- Added plugin SHA256 trust allowlist support.
- Added test runtime isolation via `CODEYZ_RUNTIME_ROOT`.

### Sprint 2 - Maintainability and reliability

- Split task run internals into package-compatible structure.
- Unified model/default settings with backward-compatible env precedence.
- Added structured JSON logging with secret redaction.
- Added request correlation ids and error payload propagation.

### Sprint 3 - Runtime scalability and isolation

- Added background autonomous job queue and cancellation API.
- Added job lifecycle state events (`queued`, `running`, `succeeded`, `failed`, `cancelled`).
- Added subprocess plugin execution mode under trusted hash config.
- Improved local retrieval scoring with phrase/symbol/recency boosts.
