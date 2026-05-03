from pathlib import Path

from scripts.release_zip import build_release_zip


def test_release_zip_with_dummy_exe(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir(parents=True)
    (tmp_path / "installer").mkdir(parents=True)
    (tmp_path / "dist" / "codeyz.exe").write_bytes(b"MZdummy")
    (tmp_path / "run.ps1").write_text("echo run", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / "VERSION").write_text("0.1.0", encoding="utf-8")
    (tmp_path / "installer" / "codeyz_installer.nsi").write_text("; nsis", encoding="utf-8")

    zip_path, size_bytes = build_release_zip(tmp_path)

    assert zip_path.exists()
    assert zip_path.name == "codeyz-v0.1.0-windows.zip"
    assert size_bytes > 0
