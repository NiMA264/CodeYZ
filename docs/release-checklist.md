# CodeYZ Beta Release Checklist

## 1. Release Preconditions

- [ ] `git status --short` ist sauber (keine unbeabsichtigten Änderungen).
- [ ] `VERSION` ist auf die Zielversion aktualisiert.
- [ ] `CHANGELOG.md` enthält die Änderungen der Zielversion.
- [ ] Keine getrackten Build-Artefakte (`node_modules/`, `dist/`, `build/`, große `.zip`-Dateien).
- [ ] Trusted Plugin Hashes wurden geprüft (`CODEYZ_TRUSTED_PLUGIN_HASHES_FILE` Inhalt/Format/Hashes aktuell).

## 2. Validation Commands

```bash
ruff check .
pytest -q
python scripts/release_check.py
```

Optional UI/Browser Smoke:

```bash
python -m playwright install chromium
pytest -q tests/test_ui_smoke.py
```

## 3. Security Verification

- [ ] Kein `shell=True` in produktivem Ausführungspfad.
- [ ] Keine sicherheitsrelevanten Pfadgrenzen via `startswith(...)`; nur kanonische Path-Boundary-Checks.
- [ ] Plugin-Trust-Datei ist valides JSON-Objekt (`{ "plugin": "sha256..." }`).
- [ ] Runtime-Isolation aktiv (Tests/Runtime schreiben nicht in ungewollte User-Pfade).
- [ ] `request_id`-Korrelation aktiv (Header + Error-Payload + strukturierte Logs).

## 4. Packaging Verification

- [ ] CLI Hilfe funktioniert:
  - `codeyz --help`
- [ ] Setup-Diagnostik funktioniert:
  - `codeyz setup`
- [ ] Server startet ohne Port-/Runtime-Fehler:
  - `codeyz server`
- [ ] Health Endpoint antwortet:
  - `GET http://127.0.0.1:8765/health`
- [ ] `version` ist im `/health`-Payload sichtbar.

## 5. Manual Smoke Test

1. [ ] Server starten: `codeyz server`
2. [ ] UI öffnen: `http://127.0.0.1:8765/ui/`
3. [ ] Autonomen Task starten (`/task/auto` via UI).
4. [ ] Status prüfen: `queued -> running -> succeeded` in Run/Timeline.
5. [ ] Cancellation prüfen:
   - Task starten
   - `POST /task/cancel/{run_id}` oder UI-Aktion
   - Status/Event zeigt `cancelled`.
6. [ ] Plugin-Ausführung prüfen (inkl. Trust-Mode falls aktiv).
7. [ ] Rollback/History prüfen (Events, Diff, Rollback-Einträge sichtbar).

## 6. Release Artifacts

Erwartete Outputs (je nach Zielplattform/-kanal):

- [ ] Python-Paket-Artefakte (wheel/sdist), falls Release-Kanal Python-Package nutzt.
- [ ] Windows EXE (falls aktiviert): `dist/codeyz.exe`
- [ ] Windows Installer (NSIS), falls aktiviert: `installer/codeyz_installer.nsi` basierter Build
- [ ] Optional Release ZIP (nur wenn bewusst erstellt und verteilt)

## 7. Rollback Guidance

- [ ] Release-Tag auf vorherige stabile Version zurücksetzen (Repo-Workflow).
- [ ] Vorherigen Installer/EXE wieder bereitstellen.
- [ ] Untrusted/fehlerhafte Plugins deaktivieren oder Trust-Hash-Datei zurückrollen.
- [ ] Logs und Run-Historie prüfen (`runtime/logs`, `runtime/runs`) und Fehlerbild dokumentieren.

## 8. Known Beta Limitations

- [ ] Local-first Architektur (kein zentraler Clusterbetrieb).
- [ ] Keine verteilten Worker; Background-Jobs laufen lokal im Prozess.
- [ ] Cancellation ist kooperativ (kein harter Kill laufender Python-Operationen).
- [ ] Retrieval ist leichtgewichtig (kein externer Vector-Store, keine verteilte Embedding-Infrastruktur).
