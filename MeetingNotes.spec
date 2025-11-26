# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\gui.py'],
    pathex=[],
    binaries=[('bin\\ffmpeg.exe', 'bin'), ('bin\\whisper-cli.exe', 'bin'), ('bin\\ggml.dll', 'bin'), ('bin\\ggml-base.dll', 'bin'), ('bin\\ggml-cpu.dll', 'bin'), ('bin\\SDL2.dll', 'bin'), ('bin\\whisper.dll', 'bin')],
    datas=[('models\\ggml-small.bin', 'models'), ('models\\ggml-base.bin', 'models'), ('prompts\\summary_default.txt', 'prompts'), ('assets\\app.png', 'assets'), ('assets\\app.ico', 'assets'), ('settings.json', '.'), ('settings_user.json', '.'), ('README.md', '.')],
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
    name='MeetingNotes',
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
    icon=['assets\\app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MeetingNotes',
)
