from __future__ import annotations

import importlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from packages.core.runtime_paths import ensure_runtime_dirs, get_env_file_path


def _status(level: str, label: str, detail: str = "", hint: str = "") -> str:
    encoding = (sys.stdout.encoding or "").lower()
    ascii_only = not encoding or "utf" not in encoding
    upper = level.upper().strip()
    if ascii_only:
        mark = {"OK": "[OK]", "WARNING": "[WARN]", "ERROR": "[FAIL]"}.get(upper, "[INFO]")
    else:
        mark = {"OK": "✔", "WARNING": "⚠", "ERROR": "✖"}.get(upper, "•")
    tail = f" - {detail}" if detail else ""
    hint_tail = f" | Hint: {hint}" if hint else ""
    return f"{mark} {label}{tail}{hint_tail}"


def _is_port_available(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _plugin_trust_status() -> tuple[str, str, str]:
    trust_path_raw = os.getenv("CODEYZ_TRUSTED_PLUGIN_HASHES_FILE")
    if trust_path_raw:
        trust_path = Path(trust_path_raw).expanduser().resolve()
    else:
        trust_path = Path(__file__).resolve().parents[2] / "plugins" / "trusted_plugins.json"
    if not trust_path.exists():
        return (
            "WARNING",
            f"Keine Trust-Datei gefunden ({trust_path})",
            "Optional: Datei mit erlaubten Plugin-Hashes anlegen.",
        )
    try:
        data = json.loads(trust_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ("ERROR", f"Trust-Datei ungültig: {exc}", "JSON prüfen (Objekt: plugin_name -> sha256).")
    if not isinstance(data, dict):
        return ("ERROR", "Trust-Datei muss JSON-Objekt sein", "Format: {\"plugin_name\": \"sha256...\"}.")
    return ("OK", f"Trust-Datei gültig ({len(data)} Einträge)", "")


def check_environment() -> list[str]:
    lines: list[str] = []
    py_ok = sys.version_info >= (3, 11)
    lines.append(
        _status(
            "OK" if py_ok else "ERROR",
            "Python >= 3.11",
            sys.version.split()[0],
            "Python 3.11+ installieren/aktivieren." if not py_ok else "",
        )
    )

    local_env = Path(".env")
    app_env = get_env_file_path()
    env_ok = local_env.exists() or app_env.exists()
    lines.append(
        _status(
            "OK" if env_ok else "WARNING",
            ".env vorhanden",
            f"local={local_env.exists()} appdata={app_env.exists()}",
            "Optional: .env anlegen (OPENAI_API_KEY=...).",
        )
    )

    key_ok = bool(os.getenv("OPENAI_API_KEY"))
    lines.append(
        _status(
            "OK" if key_ok else "ERROR",
            "OPENAI_API_KEY gesetzt",
            "",
            "Setzen via 'setx OPENAI_API_KEY \"sk-...\"' oder in %APPDATA%\\CodeYZ\\.env.",
        )
    )

    try:
        runtime_dirs = ensure_runtime_dirs()
        lines.append(_status("OK", "Runtime root schreibbar", str(runtime_dirs["root"])))
    except Exception as exc:
        lines.append(
            _status(
                "ERROR",
                "Runtime root schreibbar",
                f"Fehler: {exc}",
                "CODEYZ_RUNTIME_ROOT auf beschreibbaren Pfad setzen.",
            )
        )

    port = int(os.getenv("CODEYZ_SERVER_PORT", "8765"))
    port_ok = _is_port_available(port)
    lines.append(
        _status(
            "OK" if port_ok else "WARNING",
            f"Server-Port {port} verfügbar",
            "",
            "Anderen Port mit 'codeyz server --port <port>' nutzen." if not port_ok else "",
        )
    )

    trust_level, trust_detail, trust_hint = _plugin_trust_status()
    lines.append(_status(trust_level, "Plugin trust Konfiguration", trust_detail, trust_hint))

    venv_ok = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    lines.append(
        _status(
            "OK" if venv_ok else "WARNING",
            "Virtuelle Umgebung aktiv",
            sys.prefix,
            "Empfohlen: python -m venv .venv && .venv\\Scripts\\activate",
        )
    )
    return lines


def check_dependencies() -> list[str]:
    required = ["openai", "fastapi", "typer", "rich", "uvicorn"]

    lines: list[str] = []
    for mod in required:
        try:
            importlib.import_module(mod)
            lines.append(_status("OK", f"Dependency {mod}"))
        except Exception:
            lines.append(_status("ERROR", f"Dependency {mod}", "nicht importierbar", "pip install -e ."))
    return lines


def check_git() -> list[str]:
    lines: list[str] = []
    try:
        version = subprocess.check_output(["git", "--version"], text=True, stderr=subprocess.STDOUT).strip()
        lines.append(_status("OK", "Git installiert", version))
    except Exception:
        lines.append(_status("WARNING", "Git installiert", "git nicht gefunden", "Git installieren für Diff/Release-Checks."))
        return lines

    try:
        _ = subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], text=True, stderr=subprocess.STDOUT).strip()
        lines.append(_status("OK", "Git Repository erkannt"))
    except Exception:
        lines.append(_status("WARNING", "Git Repository erkannt", "kein git worktree", "Im Repository-Root ausführen."))
    return lines
