"""
FaceLock Independent Process Watchdog
Monitors the parent FaceLock process PID. If the parent process terminates
without writing the clean-exit marker file (e.g., killed via taskkill / Task Manager,
SIGKILL, or unhandled crash), the watchdog detects parent exit and locks the workstation.
"""
import sys
import os
import time
import logging
import argparse

logger = logging.getLogger("facelock.watchdog")

IS_WINDOWS = sys.platform == "win32"


def run_watchdog(target_pid: int, marker_path: str, simulation: bool = False) -> bool:
    """
    Blocks until target_pid exits. If marker_path exists at termination time,
    exits cleanly. Otherwise locks the workstation.
    
    Returns:
        True if clean exit was detected, False if abnormal termination triggered lock.
    """
    logger.info(f"Watchdog active: monitoring target PID {target_pid}, marker={marker_path}")

    # 1. Wait for target PID to exit
    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes

        SYNCHRONIZE = 0x00100000
        INFINITE = 0xFFFFFFFF

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, target_pid)
        if handle:
            try:
                kernel32.WaitForSingleObject(handle, INFINITE)
            finally:
                kernel32.CloseHandle(handle)
        else:
            # Process may already be dead
            pass
    else:
        while True:
            try:
                os.kill(target_pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                break
            except PermissionError:
                time.sleep(0.5)

    # 2. Allow brief filesystem flush time
    time.sleep(0.15)

    # 3. Check for clean-exit marker
    if os.path.exists(marker_path):
        logger.info(f"Target PID {target_pid} exited cleanly with marker present.")
        try:
            os.remove(marker_path)
        except OSError:
            pass
        return True
    else:
        # Abnormal termination or forced kill!
        logger.critical(
            f"TAMPER / CRASH ALERT: FaceLock process {target_pid} disappeared without clean exit marker! "
            "Locking workstation immediately."
        )
        if simulation:
            logger.info("Watchdog simulation mode: Workstation lock simulated.")
            return False

        if IS_WINDOWS:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        else:
            import subprocess
            try:
                subprocess.run(["loginctl", "lock-session"], check=False)
            except Exception as e:
                logger.error(f"Failed to execute loginctl lock-session: {e}")

        return False


def main():
    parser = argparse.ArgumentParser(description="FaceLock Process Watchdog")
    parser.add_argument("pid", type=int, help="Target FaceLock PID to monitor")
    parser.add_argument("marker", type=str, help="Absolute path to clean-exit marker file")
    parser.add_argument("--simulation", action="store_true", help="Simulate lock instead of invoking OS lock")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    clean_exit = run_watchdog(args.pid, args.marker, simulation=args.simulation)
    sys.exit(0 if clean_exit else 1)


if __name__ == "__main__":
    main()

