# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for the Tarot App.

Packages TarotApp as a Windows GUI application (onedir, no console).
Bundles the 22 Tarot card images under the media_player package path so
the frozen tarot_window module can resolve them at runtime.
"""

a = Analysis(
    ["media_player/tarot_main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("media_player/resources/tarot", "media_player/resources/tarot"),
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
    name="TarotApp",
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
    icon=["media_player/resources/tarot.ico"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TarotApp",
)