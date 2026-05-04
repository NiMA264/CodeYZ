# API Error-Code Matrix

Standard response format for API errors:

```json
{ "ok": false, "code": "...", "message": "...", "hint": "..." }
```

| code | HTTP | Bedeutung | hint |
|---|---:|---|---|
| `unsupported_model` | 400 | Angefordertes Modell ist nicht erlaubt. | Erlaubte Modelle nutzen (`gpt-5.4-mini`, `gpt-5.4`, `gpt-5.5`). |
| `unsupported_mode` | 400 | Unbekannter Composer-Modus. | Unterstützten Modus wählen. |
| `unsupported_access_level` | 400 | Unbekanntes Access-Level. | Gültiges Access-Level senden. |
| `invalid_project_path` | 400 | Projektpfad ungültig oder nicht vorhanden. | Existierenden Ordnerpfad angeben. |
| `invalid_current_project` | 400 | Current project darf nicht gesetzt werden. | Pfad zuerst zu erlaubten Projekten hinzufügen. |
| `project_tree_failed` | 400 | Dateibaum konnte nicht aufgebaut werden. | Gültiges aktuelles Projekt setzen. |
| `invalid_pinned_file` | 400 | Datei darf nicht gepinnt werden. | Nur Dateien im aktuellen Workspace pinnen. |
| `invalid_file_path` | 400 | Dateipfad ungültig/außerhalb Workspace. | Relativen Pfad im aktuellen Workspace nutzen. |
| `file_read_failed` | 400 | Datei konnte nicht gelesen werden. | Dateirechte/Encoding prüfen. |
| `context_build_failed` | 400 | Kontext aus selected/pinned files konnte nicht gebaut werden. | Datei-Grenzen und erlaubte Pfade prüfen. |
| `invalid_role_models` | 400 | Rollenspezifische Modelle sind ungültig. | Nur erlaubte Modellnamen pro Rolle setzen. |
| `autonomous_access_denied` | 403 | `/task/auto` ohne `Autonom`-Zugriff. | Access-Level auf `Autonom` setzen. |
| `plugin_not_found` | 404 | Plugin wurde nicht gefunden. | Plugin-Liste über `GET /plugins` prüfen. |
| `plugin_permission_denied` | 403 | Plugin-Scopes sind für Access-Level nicht erlaubt. | Access-Level erhöhen oder Plugin-Berechtigungen anpassen. |
| `plugin_execution_failed` | 400 | Plugin-Ausführung fehlgeschlagen. | Plugin-Input und Berechtigungen prüfen. |
| `run_not_found` | 404 | Task-Run-ID nicht gefunden. | Vorher `GET /task/runs` aufrufen. |
| `rollback_not_found` | 404 | Rollback-ID nicht gefunden. | Vorher `GET /rollback` aufrufen. |
| `validation_error` | 422 | Request-Body/Query ungültig. | Payload nach API-Schema korrigieren. |
| `http_<status>` | variabel | Fallback für nicht-semantische HTTP-Fehler. | Endpoint-spezifische Eingaben/Berechtigungen prüfen. |

