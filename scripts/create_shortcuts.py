"""
FaceLock Windows Shortcut Creator
Creates Desktop and Start Menu shortcuts with icon.ico
"""
import os
import sys
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_PYW = os.path.join(PROJECT_ROOT, ".env", "Scripts", "pythonw.exe")
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")
ICON_ICO = os.path.join(PROJECT_ROOT, "assets", "icon.ico")


def create_shortcuts():
    if sys.platform != "win32":
        print("Shortcut creation is Windows-only.")
        return

    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $StartMenu = [Environment]::GetFolderPath('Programs')
    
    # 1. Desktop Shortcut
    $Lnk1 = Join-Path $Desktop 'FaceLock.lnk'
    $sc1 = $WshShell.CreateShortcut($Lnk1)
    $sc1.TargetPath = '{VENV_PYW}'
    $sc1.Arguments = '"{MAIN_PY}"'
    $sc1.WorkingDirectory = '{PROJECT_ROOT}'
    $sc1.IconLocation = '{ICON_ICO}'
    $sc1.Description = 'FaceLock - Facial Recognition Laptop Security'
    $sc1.Save()
    Write-Host "Created Desktop shortcut: $Lnk1"

    # 2. Start Menu Shortcut
    $Lnk2 = Join-Path $StartMenu 'FaceLock.lnk'
    $sc2 = $WshShell.CreateShortcut($Lnk2)
    $sc2.TargetPath = '{VENV_PYW}'
    $sc2.Arguments = '"{MAIN_PY}"'
    $sc2.WorkingDirectory = '{PROJECT_ROOT}'
    $sc2.IconLocation = '{ICON_ICO}'
    $sc2.Description = 'FaceLock - Facial Recognition Laptop Security'
    $sc2.Save()
    Write-Host "Created Start Menu shortcut: $Lnk2"
    """

    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True)
    if res.returncode == 0:
        print(res.stdout.strip())
        print("Shortcuts successfully created.")
    else:
        print("Error creating shortcuts:", res.stderr.strip())


if __name__ == "__main__":
    create_shortcuts()
