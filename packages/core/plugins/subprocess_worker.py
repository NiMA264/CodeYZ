from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_handler(entry_path: Path):
    spec = importlib.util.spec_from_file_location(f"codeyz_plugin_subprocess_{entry_path.stem}", entry_path)
    if spec is None or spec.loader is None:
        raise ValueError("Could not load plugin module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = getattr(module, "run", None)
    if not callable(handler):
        raise ValueError("Plugin entry must define callable run(input_data)")
    return handler


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"ok": False, "error": "missing_args"}))
        return 2
    entry_path = Path(sys.argv[1]).resolve()
    payload_raw = sys.argv[2]
    input_data = json.loads(payload_raw)
    if not isinstance(input_data, dict):
        raise ValueError("Plugin input must be object")
    handler = _load_handler(entry_path)
    result = handler(input_data)
    try:
        encoded = json.dumps(result, ensure_ascii=True)
    except Exception as exc:
        raise ValueError(f"Plugin output is not JSON-serializable: {exc}") from exc
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
