"""
FaceLock Screen Lock Adapter
Handles locking the workstation across Windows and Linux platforms,
with safety simulation mode support.
"""
import logging
import platform
import subprocess
from typing import Tuple

logger = logging.getLogger("facelock.lock")
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"


def lock_workstation(simulation: bool = False, lock_mode: str = "native") -> Tuple[bool, str]:
    """
    Locks the user workstation via native OS lock or FaceLock Privacy Overlay.
    
    Args:
        simulation: If True, simulates the lock action without actually locking.
        lock_mode: "native" (Windows LockWorkStation) or "overlay" (FaceLock Auto-Unlock Screen)
        
    Returns:
        (success, message)
    """
    if simulation:
        logger.info("[SIMULATION MODE] Workstation lock triggered but suppressed by simulation mode.")
        return True, "Simulation mode: lock suppressed"

    if lock_mode == "overlay":
        logger.info("Triggering FaceLock Privacy Overlay Lock Screen.")
        from core.events import events
        events.overlay_lock_requested.emit()
        return True, "Triggered overlay privacy lock"

    if IS_WINDOWS:
        try:
            import ctypes
            result = ctypes.windll.user32.LockWorkStation()
            if result:
                logger.info("Windows LockWorkStation succeeded.")
                return True, "Locked Windows session"
            else:
                logger.error("Windows LockWorkStation failed.")
                return False, "LockWorkStation returned 0"
        except Exception as e:
            logger.exception(f"Windows lock error: {e}")
            return False, str(e)

    elif IS_LINUX:
        commands = [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "-l"],
            ["dm-tool", "lock"],
        ]
        for cmd in commands:
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=5)
                if res.returncode == 0:
                    logger.info(f"Linux lock succeeded using {' '.join(cmd)}")
                    return True, f"Locked via {cmd[0]}"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
            except Exception as e:
                logger.warning(f"Error executing {cmd}: {e}")
                continue

        logger.error("All Linux lock commands failed or were not found.")
        return False, "No compatible screen locker found"

    else:
        logger.warning(f"Unsupported OS platform for screen lock: {platform.system()}")
        return False, f"Unsupported OS: {platform.system()}"

