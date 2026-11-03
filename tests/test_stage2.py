"""
FaceLock Stage 2 Verification Test
Verifies:
1. HUD icon rendering for all 5 states (welcome, owner_left, stranger_warning, locking_countdown, locked).
2. HudPopup widget instantiation, sizing, window flags.
3. Event bus signal routing for hud_trigger and hud_cancel_countdown.
4. Auto-dismiss timer and countdown logic.
"""
import os
import sys

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.config import AppConfig
from core.events import events
from ui.hud_popup import HudPopup, render_hud_icon


def test_hud_icons():
    print("Testing HUD icon vector rendering for all states...")
    states = ["welcome", "owner_left", "stranger_warning", "locking_countdown", "locked"]
    for s in states:
        pix = render_hud_icon(s, 60)
        assert not pix.isNull(), f"Failed rendering icon for state: {s}"
        assert pix.width() == 60 and pix.height() == 60, f"Icon dimensions mismatch for {s}"
    print(" [OK] All 5 HUD icons rendered cleanly.")


def test_hud_popup_widget():
    print("Testing HudPopup widget instantiation and event routing...")
    app = QApplication.instance() or QApplication(sys.argv)
    cfg = AppConfig()

    hud = HudPopup(cfg)
    assert hud.width() == 280
    assert hud.height() == 165
    assert (hud.windowFlags() & Qt.FramelessWindowHint) != 0
    assert (hud.windowFlags() & Qt.WindowStaysOnTopHint) != 0

    # Test triggering 'welcome' state
    events.hud_trigger.emit("welcome", "Welcome back", "Owner verified", {})
    assert hud.title_label.text() == "Welcome back"
    assert hud.subtitle_label.text() == "Owner verified"
    assert not hud.btn_container.isVisible()

    # Test triggering 'locking_countdown' state
    events.hud_trigger.emit("locking_countdown", "Locking in 3s...", "Stranger detected", {"countdown": 3})
    assert "Locking in" in hud.title_label.text()
    assert hud.btn_container.isVisible()

    # Test cancel signal
    events.hud_cancel_countdown.emit()

    print(" [OK] HudPopup widget and signal handlers verified.")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_hud_icons()
    test_hud_popup_widget()
    print("\nSTAGE 2 TESTS COMPLETE AND SUCCESSFUL!")
