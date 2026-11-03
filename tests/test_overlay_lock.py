"""
Test FaceLock Overlay Lock Screen & PIN verification.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication

from core.config import AppConfig
from core.events import events
from ui.overlay_lock import OverlayLockScreen, PinDialog


def test_overlay_lock():
    print("Testing OverlayLockScreen and PIN verification...")
    app = QApplication.instance() or QApplication(sys.argv)
    cfg = AppConfig()

    # Test PIN setting & hashing
    cfg.set_pin("1234")
    assert cfg.pin_required is True
    assert cfg.verify_pin("1234") is True
    assert cfg.verify_pin("9999") is False

    # Instantiate overlay lock screen
    overlay = OverlayLockScreen(cfg)
    assert overlay is not None

    # Test lock trigger
    overlay.lock()
    assert overlay._is_active is True

    # Test unlock
    overlay.unlock()
    assert overlay._is_active is False

    # Reset pin
    cfg.set_pin("")
    assert cfg.verify_pin("anything") is True

    print(" [OK] OverlayLockScreen and PIN verification passed.")


if __name__ == "__main__":
    test_overlay_lock()
    print("\nOVERLAY LOCK SCREEN TESTS SUCCESSFUL!")

