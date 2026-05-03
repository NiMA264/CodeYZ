from packages.tools.shell import run_shell


def _summarize(text: str, max_chars: int = 2000) -> str:
    compact = (text or "").strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars] + "\n...[TRUNCATED]"


def run_tests() -> dict[str, str | bool]:
    output = run_shell("py -3.11 -m pytest")
    failed = "failed" in output.lower() or "error" in output.lower() or "no module named" in output.lower()
    return {"ok": not failed, "output": _summarize(output)}


def run_build() -> dict[str, str | bool]:
    output = run_shell("py -3.11 -m compileall packages")
    failed = "traceback" in output.lower() or "error" in output.lower()
    return {"ok": not failed, "output": _summarize(output)}


def summarize_errors(*chunks: str) -> str:
    merged = "\n\n".join(chunk for chunk in chunks if chunk)
    return _summarize(merged, max_chars=2000)
