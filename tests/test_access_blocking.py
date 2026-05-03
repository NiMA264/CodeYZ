import pytest

from packages.core.executor import run_tests
from packages.core.patcher import apply_patch
from packages.core.permissions import AUTONOMOUS, FILES, READ_ONLY, TESTS


def test_read_only_blocks_patch() -> None:
    with pytest.raises(PermissionError):
        apply_patch("README.md", "x", access_level=READ_ONLY)


def test_read_only_blocks_tests() -> None:
    with pytest.raises(PermissionError):
        run_tests(access_level=READ_ONLY)


def test_files_allows_patch_blocks_tests() -> None:
    result = apply_patch("tests/.tmp_access.txt", "ok", access_level=FILES)
    assert result["file"] == "tests/.tmp_access.txt"
    with pytest.raises(PermissionError):
        run_tests(access_level=FILES)


def test_tests_allows_tests_blocks_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.core import executor

    monkeypatch.setattr(executor, "run_shell", lambda *_args, **_kwargs: "ok")
    out = run_tests(access_level=TESTS)
    assert out["ok"] is True
    with pytest.raises(PermissionError):
        apply_patch("tests/.tmp_access2.txt", "ok", access_level=TESTS)


def test_autonomous_allows_all(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.core import executor

    monkeypatch.setattr(executor, "run_shell", lambda *_args, **_kwargs: "ok")
    out = run_tests(access_level=AUTONOMOUS)
    assert out["ok"] is True
    result = apply_patch("tests/.tmp_access3.txt", "ok", access_level=AUTONOMOUS)
    assert result["file"] == "tests/.tmp_access3.txt"
