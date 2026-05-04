import pytest

from packages.tools.git import git_commit, git_diff


def test_git_commit_without_approval_blocked() -> None:
    with pytest.raises(PermissionError):
        git_commit("msg")


def test_git_commit_with_approval_executes(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.tools import git as git_module

    called: dict[str, object] = {}

    def fake_run_shell(command: str, **kwargs):
        called["command"] = command
        called["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(git_module, "run_shell", fake_run_shell)
    out = git_module.git_commit("safe message", approved=True)
    assert out == "ok"
    assert called["command"] == 'git commit -m "safe message"'
    assert isinstance(called["kwargs"], dict)
    assert called["kwargs"].get("allow_sensitive") is True


def test_git_diff_stays_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.tools import git as git_module

    monkeypatch.setattr(git_module, "run_shell", lambda *_a, **_k: "diff-ok")
    assert git_diff() == "diff-ok"
