from __future__ import annotations

from pathlib import Path
import re


def _score_item(item: dict, terms: list[str]) -> float:
    filename = str(item.get("filename", "")).lower()
    path = str(item.get("path", "")).lower()
    content = str(item.get("content", "")).lower()
    symbols = " ".join(str(item.get("symbols", "")).lower().split())
    phrase = " ".join(terms).strip().lower()

    keyword_hits = 0
    filename_hits = 0
    path_hits = 0
    symbol_hits = 0
    for term in terms:
        keyword_hits += content.count(term)
        filename_hits += filename.count(term)
        path_hits += path.count(term)
        symbol_hits += symbols.count(term)

    exact_phrase_boost = 6 if phrase and phrase in content else 0
    symbol_name_boost = 0
    if phrase:
        symbol_name_boost = 8 if re.search(rf"\b{re.escape(phrase)}\b", symbols) else 0

    depth = max(len(Path(path).parts), 1)
    shorter_path_bonus = 1.0 / depth
    recency_boost = float(item.get("modified_ts", 0.0) or 0.0) / 1_000_000_000_000.0
    return float(
        keyword_hits
        + (filename_hits * 3)
        + (path_hits * 1.5)
        + (symbol_hits * 2)
        + exact_phrase_boost
        + symbol_name_boost
        + shorter_path_bonus
        + recency_boost
    )


def rank_files(files: list[dict], query: str) -> list[dict]:
    terms = [part.strip().lower() for part in query.split() if part.strip()]
    if not terms:
        return files

    scored: list[tuple[float, dict]] = []
    for item in files:
        score = _score_item(item, terms)
        if score > 0:
            with_score = dict(item)
            with_score["score"] = round(score, 4)
            scored.append((score, with_score))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored]
