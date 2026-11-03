# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Specification for FaceLock
Builds a standalone, single-folder Windows distribution with macOS-styled native UI.
"""
import os
import sys

block_cipher = None
PROJECT_ROOT = os.path.abspath(SPECPATH) if 'SPECPATH' in globals() else os.path.abspath(os.getcwd())

added_datas = [
    (os.path.join(PROJECT_ROOT, 'assets'), 'assets'),
]

hidden_imports = [
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'cryptography',
    'cryptography.fernet',
    'keyring',
    'keyring.backends',
    'cv2',
    'numpy',
]

# Windows Credential Manager is only present on Windows. Keeping this import
# out of Linux analysis allows the same spec to produce native builds on both.
if sys.platform == 'win32':
    hidden_imports.append('keyring.backends.Windows')

excluded_modules = [
    'tkinter',
    'matplotlib',
    'scipy',
    'test',
    'unittest',
]

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FaceLock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Native GUI without console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'assets', 'icon.ico') if sys.platform == 'win32' else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FaceLock',
)
