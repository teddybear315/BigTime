# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['client_main.py'],
    pathex=[],
    binaries=[],
    datas=[('ico.ico', '.'), ('shared', 'shared'), ('client', 'client'), ('ui', 'ui')],
    hiddenimports=[
        'PyQt6',
        'requests',
        'reportlab',
        'PIL',  # Required by reportlab
        'zoneinfo',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'flask',
        'flask_cors',
        'waitress',
        'ntplib',
        'tkinter',
        'matplotlib',
        'numpy',
        'test',
        'unittest',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BigTime',
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
