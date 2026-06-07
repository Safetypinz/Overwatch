# PyInstaller spec for Overwatch. Build on Windows: see build.ps1.
# Produces a single-file dist\Overwatch.exe (windowed / tray app, no console).

block_cipher = None

a = Analysis(
    ['run_winmon.py'],
    pathex=[],
    binaries=[],
    # The web dashboard is loaded from winmon/api/static via
    # Path(__file__).parent / "static", so it must ship at the same relative path.
    datas=[('winmon/api/static', 'winmon/api/static')],
    hiddenimports=[
        # WMI / COM / pywin32 (imported dynamically inside monitor threads + service)
        'wmi', 'pythoncom', 'pywintypes', 'win32timezone',
        'win32api', 'win32con', 'win32event', 'win32evtlog', 'win32ts',
        'win32service', 'win32serviceutil', 'servicemanager', 'win32com',
        # runtime + UI
        'psutil', 'pystray', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'webview',
        # web stack (uvicorn pulls these dynamically)
        'fastapi', 'uvicorn',
        'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan', 'uvicorn.lifespan.on',
        # our own packages (dynamic imports in places)
        'winmon', 'winmon.monitors', 'winmon.intel', 'winmon.system', 'winmon.gui',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='Overwatch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,          # tray app — no console window
    icon='Overwatch.ico',
)
