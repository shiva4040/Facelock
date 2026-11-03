@echo off
title FaceLock
cd /d "%~dp0"

:: ----------------------------------------------------
:: FaceLock Windows Launcher
:: Automatically finds virtual environment or system Python
:: and launches FaceLock.
:: ----------------------------------------------------

set "PYTHON_EXEC="

:: 1. Check local virtual environment (.env)
if exist ".env\Scripts\python.exe" (
    set "PYTHON_EXEC=.env\Scripts\python.exe"
    goto :LAUNCH
)

:: 2. Check alternative virtual environment (venv)
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
    goto :LAUNCH
)

:: 3. Check system Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXEC=python"
    goto :LAUNCH
)

:: Python not detected
echo [ERROR] Python was not found on your system or in the .env virtual environment.
echo Please ensure Python 3.11+ is installed and added to your PATH.
echo.
pause
exit /b 1

:LAUNCH
echo Starting FaceLock...
"%PYTHON_EXEC%" main.py

:: If exited with error, keep window open to display traceback
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] FaceLock stopped unexpectedly (exit code: %errorlevel%).
    pause
)

