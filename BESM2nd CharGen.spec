# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['BESM2nd CharGen.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('besm2nd_config_eng.toml', '.'),
        ('besm2nd_config_fra.toml', '.'),
        ('BESM2_Retro_logo_dtrpg_250px.png', '.'),
        ('BESM2nd Native Arsenal.json', '.'),
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
    a.binaries,
    a.datas,
    [],
    name='BESM2nd CharGen',
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
)
