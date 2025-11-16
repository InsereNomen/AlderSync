# -*- mode: python ; coding: utf-8 -*-
"""
AlderSync Client - PyInstaller Spec File

This spec file defines how PyInstaller builds the AlderSync client executable.
It bundles all dependencies and creates a standalone executable for distribution.

Usage:
    pyinstaller aldersync.spec

Output:
    - Windows: dist/aldersync.exe
    - Mac: dist/aldersync.app
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Get the absolute path to the icon file
# SPECPATH is a PyInstaller variable containing the directory of this spec file
ICON_PATH = os.path.join(SPECPATH, 'aldersync_icon.ico')

# Collect all keyring backends and dependencies
# keyring uses dynamic imports that PyInstaller can't auto-detect
keyring_datas, keyring_binaries, keyring_hiddenimports = collect_all('keyring')

# Additional hidden imports that PyInstaller might miss
hidden_imports = [
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'keyring.backends.macOS',
    'keyring.backends.SecretService',
    'keyring.backends.chainer',
    'psutil',
    'requests',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    'tkinter.scrolledtext',
] + keyring_hiddenimports

# Determine platform-specific settings
if sys.platform == 'win32':
    # Windows-specific hidden imports
    hidden_imports.extend([
        'win32ctypes',
        'win32ctypes.core',
    ])
elif sys.platform == 'darwin':
    # Mac-specific hidden imports
    hidden_imports.extend([
        'Foundation',
        'AppKit',
    ])

a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=keyring_binaries,
    datas=keyring_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='aldersync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - GUI has log panel, CLI writes to file
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH if sys.platform == 'win32' else None,
)

# Mac-specific bundle (only on macOS)
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='AlderSync.app',
        # icon='icon.icns',  # Uncomment when icon is available
        bundle_identifier='com.aldersync.client',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'CFBundleName': 'AlderSync',
            'CFBundleDisplayName': 'AlderSync',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHumanReadableCopyright': 'AlderSync Project',
        },
    )
