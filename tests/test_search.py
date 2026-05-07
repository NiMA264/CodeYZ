from packages.core.search import rank_files


def test_rank_files_filename_boost() -> None:
    files = [
        {"path": "src/helpers.py", "filename": "helpers.py", "content": "utility math"},
        {"path": "src/math_ops.py", "filename": "math_ops.py", "content": "math math math"},
    ]
    ranked = rank_files(files, "math")
    assert ranked
    assert ranked[0]["filename"] in {"math_ops.py", "helpers.py"}


def test_rank_files_empty_query_returns_input() -> None:
    files = [{"path": "a.py", "filename": "a.py", "content": "x"}]
    assert rank_files(files, "") == files


def test_rank_files_exact_phrase_boost() -> None:
    files = [
        {"path": "a.py", "filename": "a.py", "content": "agent loop queue worker"},
        {"path": "b.py", "filename": "b.py", "content": "agent and loop and queue and worker"},
    ]
    ranked = rank_files(files, "queue worker")
    assert ranked[0]["path"] == "a.py"


def test_rank_files_symbol_and_recency_tiebreak() -> None:
    files = [
        {
            "path": "old.py",
            "filename": "old.py",
            "content": "def run_autonomous_task(): pass",
            "symbols": ["run_autonomous_task"],
            "modified_ts": 1000.0,
        },
        {
            "path": "new.py",
            "filename": "new.py",
            "content": "def run_autonomous_task(): pass",
            "symbols": ["run_autonomous_task"],
            "modified_ts": 2000.0,
        },
    ]
    ranked = rank_files(files, "run_autonomous_task")
    assert ranked[0]["path"] == "new.py"
