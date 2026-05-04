from __future__ import annotations

CODE_KEYWORDS = {
    "code",
    "datei",
    "file",
    "bug",
    "fehler",
    "test",
    "build",
    "workspace",
    "analysiere projekt",
    "analysiere das projekt",
    "refactor",
    "endpoint",
    "funktion",
    "klasse",
}

CREATIVE_KEYWORDS = {
    "logo",
    "bild",
    "design",
    "farbe",
    "branding",
    "visual",
    "3d",
    "icon",
    "svg",
}

CONTEXT_MODES = {"Projekt planen", "Code", "Fix", "Review"}


def is_creative_request(message: str) -> bool:
    lowered = (message or "").lower()
    return any(token in lowered for token in CREATIVE_KEYWORDS)


def is_code_request(message: str) -> bool:
    lowered = (message or "").lower()
    return any(token in lowered for token in CODE_KEYWORDS)


def should_attach_code_context(
    message: str,
    mode: str | None,
    selected_file: str | None = None,
    pinned_count: int = 0,
) -> bool:
    if mode in CONTEXT_MODES:
        return True
    if selected_file or pinned_count > 0:
        return True
    if mode == "Chat" and is_creative_request(message):
        return False
    return is_code_request(message)
