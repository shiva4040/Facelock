@echo off
setlocal enabledelayedexpansion
title FaceLock Installer (Windows)
cd /d "%~dp0"

echo ===================================================================
echo               FaceLock Windows App Installer v1.0
echo       macOS-styled facial recognition security for your laptop
echo ===================================================================
echo.

:: 1. Check Python
set "SYS_PYTHON="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "SYS_PYTHON=python"
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "SYS_PYTHON=py -3"
    )
)

if "%SYS_PYTHON%"=="" (
    echo [ERROR] Python 3 was not found on your system PATH.
    echo Please install Python 3.10 or higher from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking Python installation...
%SYS_PYTHON% --version
if %errorlevel% neq 0 (
    echo [ERROR] Failed to run Python. Please check your Python installation.
    pause
    exit /b 1
)

:: 2. Setup Virtual Environment
echo.
echo [2/5] Setting up isolated Python virtual environment (.env)...
if not exist ".env\Scripts\python.exe" (
    echo Creating virtual environment in %~dp0.env ...
    %SYS_PYTHON% -m venv .env
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Existing virtual environment found.
)

set "VENV_PY=.env\Scripts\python.exe"
set "VENV_PYW=.env\Scripts\pythonw.exe"

:: 3. Install Dependencies
echo.
echo [3/5] Installing dependencies (PySide6, OpenCV, Cryptography)...
"%VENV_PY%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PY%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install required dependencies.
    pause
    exit /b 1
)

:: Also install package locally so 'facelock' command is registered
"%VENV_PY%" -m pip install -e . >nul 2>&1

:: 4. Pre-download AI Models (YuNet Face Detector & SFace Recognizer)
echo.
echo [4/5] Verifying on-device neural network models (YuNet + SFace)...
"%VENV_PY%" -c "from core.detector import check_and_download_models; d, r = check_and_download_models(); print('  Models verified at:\n  - ' + d + '\n  - ' + r)"
if %errorlevel% neq 0 (
    echo [WARNING] Could not pre-download models now. They will download automatically on first launch.
)

:: 5. Create Desktop and Start Menu Shortcuts
echo.
echo [5/5] Creating application shortcuts with app icon...
"%VENV_PY%" scripts\create_shortcuts.py

echo.
echo ===================================================================
echo                     INSTALLATION COMPLETE!
echo.
echo FaceLock has been installed successfully.
echo You can launch FaceLock anytime via:
echo   1. Desktop Shortcut ("FaceLock")
echo   2. Windows Start Menu ("FaceLock")
echo   3. Running: run.bat or run_silent.bat
echo ===================================================================
echo.

set /p "LAUNCH_NOW=Would you like to launch FaceLock now? [Y/N]: "
if /i "%LAUNCH_NOW%"=="Y" (
    echo Starting FaceLock in background...
    start "" "%VENV_PYW%" main.py
)

exit /b 0
