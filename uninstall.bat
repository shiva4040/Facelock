@echo off
setlocal enabledelayedexpansion
title FaceLock Uninstaller (Windows)
cd /d "%~dp0"

echo ===================================================================
echo               FaceLock Windows App Uninstaller
echo ===================================================================
echo.

set /p "CONFIRM=Are you sure you want to uninstall FaceLock? [Y/N]: "
if /i not "%CONFIRM%"=="Y" (
    echo Uninstallation cancelled.
    pause
    exit /b 0
)

echo.
echo [1/4] Closing any running FaceLock instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' -or $_.CommandLine -like '*FaceLock*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo [2/4] Removing Desktop and Start Menu shortcuts...
if exist ".env\Scripts\python.exe" (
    .env\Scripts\python.exe scripts\remove_shortcuts.py
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$d = [Environment]::GetFolderPath('Desktop'); $m = [Environment]::GetFolderPath('Programs'); Remove-Item -Force \"$d\FaceLock.lnk\" -ErrorAction SilentlyContinue; Remove-Item -Force \"$m\FaceLock.lnk\" -ErrorAction SilentlyContinue"
)

echo.
echo [3/4] User Data and Configuration:
set /p "DEL_DATA=Do you want to delete all saved face data, intruder snapshots, and settings (~/.facelock)? [Y/N]: "
if /i "%DEL_DATA%"=="Y" (
    if exist "%USERPROFILE%\.facelock" (
        echo Removing %USERPROFILE%\.facelock ...
        rd /s /q "%USERPROFILE%\.facelock" >nul 2>&1
        echo   Face data and settings wiped.
    )
) else (
    echo   Keeping face data and settings for future reinstall.
)

echo.
echo [4/4] Python Environment:
set /p "DEL_ENV=Do you want to remove the local virtual environment (.env)? [Y/N]: "
if /i "%DEL_ENV%"=="Y" (
    if exist ".env" (
        echo Removing virtual environment (.env)...
        rd /s /q ".env" >nul 2>&1
        echo   Virtual environment removed.
    )
)

echo.
echo ===================================================================
echo                     UNINSTALLATION COMPLETE
echo FaceLock has been removed from your system.
echo ===================================================================
echo.
pause
exit /b 0
