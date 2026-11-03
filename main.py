"""
FaceLock - macOS-Styled Facial Recognition Security System
Application entry point with QLockFile single-instance guard, logging setup,
background worker management, system tray, HUD overlay, and graceful shutdown.
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PySide6.QtCore import Qt, QLockFile, QDir
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from core.config import AppConfig, DEFAULT_BASE_DIR, LOG_FILE, LOCK_FILE, CLEAN_EXIT_MARKER
from core.events import events
from core.worker import FaceLockWorker
from core.lock import lock_workstation
from ui.main_window import MainWindow
from ui.live_activity import LiveActivityBar
from ui.overlay_lock import OverlayLockScreen
from ui.tray import FaceLockTray, create_tray_pixmap


def setup_logging():
    os.makedirs(DEFAULT_BASE_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )


def main():
    setup_logging()
    logger = logging.getLogger("facelock.main")
    logger.info("Starting FaceLock Application...")

    # Qt Application Setup
    app = QApplication(sys.argv)
    app.setApplicationName("FaceLock")
    app.setOrganizationName("FaceLock")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Single-instance guard
    lock_file = QLockFile(LOCK_FILE)
    lock_file.setStaleLockTime(5000)
    if not lock_file.tryLock(100):
        logger.warning("Another instance of FaceLock is already running. Exiting.")
        sys.exit(0)

    # Load configuration
    config = AppConfig.load()

    # Create UI Components
    main_window = MainWindow(config)
    def open_activity_from_live():
        main_window.showNormal()
        main_window.raise_()
        main_window.activateWindow()
        main_window.sidebar.select_page(3)

    floating_activity = LiveActivityBar(
        config,
        on_open_activity=open_activity_from_live,
        floating=True,
    )
    overlay_lock = OverlayLockScreen(config)
    tray = FaceLockTray(config)

    # Initialize Background Monitoring Worker
    worker = FaceLockWorker(config)
    main_window.owner_face_page.set_monitoring_worker(worker)

    # Wiring Callbacks & Signals
    def toggle_window():
        if main_window.isVisible():
            main_window.hide()
        else:
            main_window.showNormal()
            main_window.raise_()
            main_window.activateWindow()

    def toggle_protect():
        new_state = not config.protection_enabled
        config.update(protection_enabled=new_state)
        if new_state:
            worker.resume()
        else:
            worker.pause()

    def simulate_lock():
        logger.info("Simulating screen lock from tray.")
        events.hud_trigger.emit("locked", "Screen Locked (Sim)", "Simulation trigger", {})
        lock_workstation(simulation=True, lock_mode=config.lock_mode)

    def lock_now():
        logger.info("User requested immediate lock from tray.")
        lock_workstation(simulation=config.simulation_mode, lock_mode=config.lock_mode)

    tray.set_callbacks(
        toggle_window=toggle_window,
        toggle_protect=toggle_protect,
        simulate_lock=simulate_lock,
        lock_now=lock_now
    )

    # HUD countdown cancel signal wiring
    events.hud_cancel_countdown.connect(worker.cancel_countdown)

    # Start worker thread
    worker.start()

    # Clear stale exit marker if left from dirty shutdown
    if os.path.exists(CLEAN_EXIT_MARKER):
        try:
            os.remove(CLEAN_EXIT_MARKER)
        except OSError:
            pass

    # Launch security watchdog process if enabled
    watchdog_proc = None
    if config.watchdog_enabled:
        try:
            import subprocess
            watchdog_cmd = [
                sys.executable,
                "-m",
                "core.watchdog",
                str(os.getpid()),
                CLEAN_EXIT_MARKER,
            ]
            if config.simulation_mode:
                watchdog_cmd.append("--simulation")

            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            watchdog_proc = subprocess.Popen(watchdog_cmd, creationflags=creationflags)
            logger.info(f"Spawned FaceLock Watchdog process PID {watchdog_proc.pid}")
        except Exception as e:
            logger.error(f"Failed to launch watchdog: {e}")

    # Graceful shutdown handler
    def cleanup():
        logger.info("Shutting down FaceLock...")
        # Mark clean exit so watchdog terminates quietly without locking
        try:
            with open(CLEAN_EXIT_MARKER, "w") as f:
                f.write(str(os.getpid()))
            logger.info("Wrote clean exit marker.")
        except Exception as ex:
            logger.error(f"Failed to write clean exit marker: {ex}")

        worker.stop()
        lock_file.unlock()
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
        logger.info("Shutdown completed.")

    app.aboutToQuit.connect(cleanup)

    # Display UI
    tray.show()
    if not config.start_minimized:
        main_window.show()
    else:
        events.window_visibility_changed.emit(False)

    logger.info("FaceLock UI event loop initialized.")
    exit_code = app.exec()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
