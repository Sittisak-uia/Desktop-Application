# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Task Manager PRO.

Packages TaskManagerPRO as a Windows GUI application (onedir, no console).
Bundles application resources and sets the windowed executable icon.
"""

a = Analysis(
    ["task_manager/main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("task_manager/resources", "task_manager/resources"),
    ],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name="TaskManagerPRO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["task_manager/resources/icon.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TaskManagerPRO",
)
