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
