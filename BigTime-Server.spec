# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['server\\server_tray.py'],
    pathex=[],
    binaries=[],
    datas=[('ico.ico', '.'), ('shared', 'shared'), ('client', 'client'), ('server', 'server'), ('ui', 'ui')],
    hiddenimports=[
        'PyQt6',
        'flask',
        'flask_cors',
        'waitress',
        'requests',
        'ntplib',
        'reportlab',
        'PIL',  # Required by reportlab
        'zoneinfo',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'test',
        'unittest',
    ],
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
    name='BigTime-Server',
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
    icon=['ico.ico'],
)
