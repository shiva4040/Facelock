"""
FaceLock Stage 3 & 4 Verification Test
Verifies:
1. All custom UI components: MacToggle, PillButton, MacCard, RingProgress, CameraView, TrafficLights.
2. All 5 pages: DashboardPage, OwnerFacePage, SecurityPage, IntruderLogPage, SettingsPage.
3. Sidebar and MainWindow integration.
4. Theming tokens and style generation.
"""
import os
import sys

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication

from core.config import AppConfig
from ui.theme import ThemeTokens, is_system_dark_mode
from ui.components.toggle import MacToggle
from ui.components.pill_button import PillButton
from ui.components.card import MacCard, SettingsRow
from ui.components.status_ring import StatusRing
from ui.components.camera_view import CameraView
from ui.components.traffic_lights import TrafficLights
from ui.sidebar import Sidebar
from ui.main_window import MainWindow


def test_theme():
    print("Testing macOS theme tokens...")
    dark = ThemeTokens("dark")
    assert dark.is_dark is True
    assert "#" in dark.accent
    qss_dark = dark.get_stylesheet()
    assert "QMainWindow" in qss_dark

    light = ThemeTokens("light")
    assert light.is_dark is False
    assert "#" in light.accent
    print(" [OK] Theme tokens passed.")


def test_custom_components():
    app = QApplication.instance() or QApplication(sys.argv)
    print("Testing custom macOS components...")
    # Toggle
    toggle = MacToggle(checked=False)
    assert not toggle.isChecked()
    toggle.setChecked(True)
    assert toggle.isChecked()

    # PillButton
    btn = PillButton("Test Pill", variant="primary")
    assert btn.text() == "Test Pill"
    btn.set_variant("danger")
    assert btn.variant == "danger"

    # Card and Row
    card = MacCard()
    row = SettingsRow("Title", "Subtitle", toggle)
    assert row.title_label.text() == "Title"

    # StatusRing
    ring = StatusRing(size=88, status="protected")
    assert ring.width() == 88
    ring.setStatus("paused")
    assert ring._status == "paused"

    # CameraView
    cam = CameraView(circular_mask=True)
    assert cam.circular_mask is True

    # TrafficLights
    tl = TrafficLights()
    assert tl.width() == 68

    print(" [OK] Custom macOS components passed.")


def test_main_window_and_pages():
    print("Testing MainWindow and all 5 settings pages...")
    cfg = AppConfig()
    win = MainWindow(cfg)
    assert win.width() >= 780
    assert win.content_stack.count() == 5

    # Switch through each page
    for i in range(5):
        win.sidebar.select_page(i)
        assert win.content_stack.currentIndex() == i

    assert win.dashboard_page is not None
    assert win.owner_face_page is not None
    assert win.security_page is not None
    assert win.intruder_log_page is not None
    assert win.settings_page is not None

    print(" [OK] MainWindow and all 5 pages verified successfully.")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_theme()
    test_custom_components()
    test_main_window_and_pages()
    print("\nSTAGE 3 & 4 TESTS COMPLETE AND SUCCESSFUL!")

