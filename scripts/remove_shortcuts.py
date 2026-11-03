"""
FaceLock Windows Shortcut Remover
Removes Desktop and Start Menu shortcuts cleanly
"""
import os
import sys
import subprocess


def remove_shortcuts():
    if sys.platform != "win32":
        return

    ps_script = """
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $StartMenu = [Environment]::GetFolderPath('Programs')
    
    $f1 = Join-Path $Desktop 'FaceLock.lnk'
    $f2 = Join-Path $StartMenu 'FaceLock.lnk'
    
    if (Test-Path $f1) { Remove-Item -Force $f1; Write-Host "  Removed: $f1" }
    if (Test-Path $f2) { Remove-Item -Force $f2; Write-Host "  Removed: $f2" }
    """

    res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True)
    if res.returncode == 0:
        print(res.stdout.strip())
        print("Shortcuts removed.")
    else:
        print("Error removing shortcuts:", res.stderr.strip())


if __name__ == "__main__":
    remove_shortcuts()
