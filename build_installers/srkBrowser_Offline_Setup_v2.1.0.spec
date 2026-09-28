# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/Muhammad_Shofiqul/Desktop/SRK/build_installers/installer_offline.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/Muhammad_Shofiqul/Desktop/srkBrowser_v2.1.0_Portable.zip', '.')],
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
    a.binaries,
    a.datas,
    [],
    name='srkBrowser_Offline_Setup_v2.1.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/Muhammad_Shofiqul/Desktop/SRK/data/assets/app_icon.ico'],
)
