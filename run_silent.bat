@echo off
cd /d "%~dp0"

:: ----------------------------------------------------
:: FaceLock Silent Background Launcher (No Console Window)
:: ----------------------------------------------------

:: 1. If compiled executable exists, run it directly
if exist "dist\FaceLock\FaceLock.exe" (
    start "" "dist\FaceLock\FaceLock.exe"
    exit /b 0
)

:: 2. Use pythonw from .env
if exist ".env\Scripts\pythonw.exe" (
    start "" ".env\Scripts\pythonw.exe" main.py
    exit /b 0
)

:: 3. Fallback to system pythonw
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw main.py
    exit /b 0
)

:: 4. Fallback to regular python if pythonw is not found
call run.bat

