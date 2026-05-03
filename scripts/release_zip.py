from __future__ import annotations

import zipfile
from pathlib import Path


def build_release_zip(project_root: Path | None = None) -> tuple[Path, int]:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    exe = root / "dist" / "codeyz.exe"
    if not exe.exists():
        raise FileNotFoundError("dist/codeyz.exe not found. Build exe first.")

    version_file = root / "VERSION"
    if not version_file.exists():
        raise FileNotFoundError("VERSION file missing")
    version = version_file.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError("VERSION is empty")

    release_dir = root / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    zip_path = release_dir / f"codeyz-v{version}-windows.zip"
    candidates = [
        (exe, "codeyz.exe"),
        (root / "run.ps1", "run.ps1"),
        (root / "README.md", "README.md"),
        (version_file, "VERSION"),
        (root / "installer" / "codeyz_installer.nsi", "installer/codeyz_installer.nsi"),
    ]

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname in candidates:
            if source.exists() and source.is_file():
                zf.write(source, arcname)

    size_bytes = zip_path.stat().st_size
    return zip_path, size_bytes


def main() -> int:
    try:
        zip_path, size_bytes = build_release_zip()
    except Exception as exc:
        print(f"Release ZIP failed: {exc}")
        return 1

    print(f"Release ZIP: {zip_path}")
    print(f"Size: {size_bytes} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
