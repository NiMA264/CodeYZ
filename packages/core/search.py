from __future__ import annotations

from pathlib import Path


def _score_item(item: dict, terms: list[str]) -> float:
    filename = str(item.get("filename", "")).lower()
    path = str(item.get("path", "")).lower()
    content = str(item.get("content", "")).lower()

    keyword_hits = 0
    filename_hits = 0
    path_hits = 0
    for term in terms:
        keyword_hits += content.count(term)
        filename_hits += filename.count(term)
        path_hits += path.count(term)

    depth = max(len(Path(path).parts), 1)
    shorter_path_bonus = 1.0 / depth
    return float(keyword_hits + (filename_hits * 3) + (path_hits * 1.5) + shorter_path_bonus)


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
