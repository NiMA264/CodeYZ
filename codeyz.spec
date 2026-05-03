# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['F:\\Projekte\\CodeYZ\\packages\\cli\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('F:\\Projekte\\CodeYZ\\VERSION', '.'), ('F:\\Projekte\\CodeYZ\\packages\\server\\static', 'packages/server/static')],
    hiddenimports=['fastapi', 'uvicorn', 'typer', 'rich', 'packages.server.app', 'packages.server.routes_plugins', 'packages.server.routes_projects', 'packages.server.routes_task', 'packages.server.routes_rollback', 'packages.core.plugins.plugin_loader', 'packages.core.plugins.plugin_registry', 'packages.core.plugins.plugin_permissions'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='codeyz',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
