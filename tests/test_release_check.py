from __future__ import annotations

from scripts.release_check import ROOT, check_artifact_hygiene


def test_release_check_catches_forbidden_tracked_artifacts(monkeypatch) -> None:
    (ROOT / "node_modules").mkdir(exist_ok=True)
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "node_modules" / "x.js").write_text("x", encoding="utf-8")
    (ROOT / "dist" / "codeyz.exe").write_text("x", encoding="utf-8")
    (ROOT / "build" / "tmp.txt").write_text("x", encoding="utf-8")
    (ROOT / "ok.py").write_text("x", encoding="utf-8")

    def fake_run(cmd):
        if cmd[:2] == ["git", "ls-files"]:
            return 0, "node_modules/x.js\ndist/codeyz.exe\nbuild/tmp.txt\nok.py"
        if cmd[:3] == ["git", "cat-file", "-s"]:
            return 0, "10"
        return 0, ""

    monkeypatch.setattr("scripts.release_check._run", fake_run)
    errors = check_artifact_hygiene()
    assert errors
    assert "Banned tracked artifacts" in errors[0]

    for rel in ["node_modules/x.js", "dist/codeyz.exe", "build/tmp.txt", "ok.py"]:
        p = ROOT / rel
        if p.exists():
            p.unlink()
    for rel in ["node_modules", "dist", "build"]:
        p = ROOT / rel
        if p.exists():
            p.rmdir()
