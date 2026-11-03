"""
Unit Tests for Stage 1: Design Tokens, Shell, Sidebar, and Components
Validates token values, contrast ratios, geometry, accessibility,
and component state transitions.
"""
import sys
import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ui.theme import ThemeTokens, is_system_dark_mode
from ui.strings import Strings
from ui.components.toggle import MacToggle
from ui.components.segmented import SegmentedControl
from ui.components.pill_button import PillButton
from ui.components.card import MacCard, SettingsRow
from ui.components.badge import Badge
from ui.components.stepper import Stepper
from ui.components.slider import LabeledSlider
from ui.components.status_ring import StatusRing
from ui.sidebar import Sidebar, render_app_badge, render_sidebar_icon
from ui.main_window import MainWindow
from core.config import AppConfig


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    return app


class TestThemeTokens:
    def test_light_mode_tokens_exact_match(self):
        t = ThemeTokens("light")
        assert t.window_bg == "#F5F5F7"
        assert t.sidebar_bg == "#ECECF0"
        assert t.sidebar_border == "#DCDCE2"
        assert t.card_bg == "#FFFFFF"
        assert t.card_border == "#E4E4E8"
        assert t.row_divider == "#EDEDF0"
        assert t.control_border == "#CFCFD6"
        assert t.text_primary == "#1D1D1F"
        assert t.text_secondary == "#5C5C63"
        assert t.accent == "#0066D6"
        assert t.accent_soft == "#D5E5FA"
        assert t.accent_text_on_soft == "#0B4FA8"
        assert t.success == "#1B7F45"
        assert t.danger == "#C4001A"
        assert t.warning == "#8A5300"
        assert t.danger_outline == "#E8B4BB"
        assert t.toggle_off == "#8E8E93"
        assert t.segmented_track == "#E6E6EA"
        assert t.info_banner_bg == "#E6F0FC"
        assert t.info_banner_text == "#0B3F8A"
        assert t.preview_dark == "#2C2C30"

    def test_radii_and_metrics(self):
        t = ThemeTokens("light")
        assert t.radius_window == 12
        assert t.radius_hero_card == 16
        assert t.radius_card == 12
        assert t.radius_segmented == 9
        assert t.radius_segmented_inner == 7
        assert t.radius_toggle == 13
        assert t.spacing_grid == 8
        assert t.page_padding_v == 28
        assert t.page_padding_h == 32

    def test_dark_mode_contrast_ratio(self):
        def luminance(color_hex: str) -> float:
            c = QColor(color_hex)
            r = c.redF()
            g = c.greenF()
            b = c.blueF()
            def channel(v):
                return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

        def contrast_ratio(hex1: str, hex2: str) -> float:
            l1 = luminance(hex1)
            l2 = luminance(hex2)
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        t_dark = ThemeTokens("dark")
        # Text secondary on card bg must exceed 4.5:1
        ratio = contrast_ratio(t_dark.text_secondary, t_dark.card_bg)
        assert ratio >= 4.5, f"Contrast ratio {ratio:.2f} is below 4.5:1 requirement"


class TestStringsModule:
    def test_zero_em_dashes_in_copy(self):
        for attr in dir(Strings):
            if attr.isupper():
                val = getattr(Strings, attr)
                if isinstance(val, str):
                    assert "—" not in val, f"Strings.{attr} contains em dash '—'"
                    assert "–" not in val, f"Strings.{attr} contains en dash '–'"


class TestComponents(object):
    def test_mac_toggle(self, qapp):
        toggle = MacToggle(checked=False)
        assert toggle.width() == 42
        assert toggle.height() == 26
        assert not toggle.isChecked()
        assert toggle.accessibleDescription() == "unchecked"

        toggle.setChecked(True)
        assert toggle.isChecked()
        assert toggle.accessibleDescription() == "checked"

    def test_segmented_control(self, qapp):
        items = ["Relaxed", "Balanced", "Strict"]
        seg = SegmentedControl(items=items, default_index=1)
        assert seg.currentIndex() == 1
        assert seg.currentText() == "Balanced"

        seg.setCurrentIndex(2)
        assert seg.currentIndex() == 2
        assert seg.currentText() == "Strict"

    def test_pill_button_variants(self, qapp):
        btn = PillButton("Action", variant="primary")
        assert btn.height() == 32
        assert btn.variant == "primary"

        btn.set_variant("secondary")
        assert btn.variant == "secondary"

        btn.set_variant("danger")
        assert btn.variant == "danger"

    def test_stepper_bounds_and_stepping(self, qapp):
        stepper = Stepper(value=2, min_value=1, max_value=10)
        assert stepper.value() == 2

        stepper._increment()
        assert stepper.value() == 3

        stepper._decrement()
        assert stepper.value() == 2

        # Clamp at min
        stepper.setValue(1)
        stepper._decrement()
        assert stepper.value() == 1

        # Clamp at max
        stepper.setValue(10)
        stepper._increment()
        assert stepper.value() == 10

    def test_labeled_slider_mapping(self, qapp):
        slider = LabeledSlider(value=0.40, min_value=0.25, max_value=0.70, step=0.01)
        assert pytest.approx(slider.value(), abs=0.01) == 0.40
        assert slider.val_label.text() == "0.40"

        slider.setValue(0.55)
        assert pytest.approx(slider.value(), abs=0.01) == 0.55
        assert slider.val_label.text() == "0.55"

    def test_status_ring_states(self, qapp):
        ring = StatusRing(size=88, status="protected")
        assert ring.width() == 88
        assert ring._status == "protected"

        ring.setStatus("intruder")
        assert ring._status == "intruder"

    def test_badge_variants(self, qapp):
        b = Badge("Beta", variant="beta")
        assert b.text() == "Beta"


class TestShellAndSidebar(object):
    def test_sidebar_geometry_and_nav(self, qapp):
        sidebar = Sidebar()
        assert sidebar.width() == 220
        assert len(sidebar._buttons) == 4
        assert sidebar._buttons[0].text() == "Dashboard"
        assert sidebar._buttons[1].text() == "Owner Face"
        assert sidebar._buttons[2].text() == "Security"
        assert sidebar._buttons[3].text() == "Activity"

    def test_main_window_shell_dimensions(self, qapp):
        cfg = AppConfig(simulation_mode=True)
        win = MainWindow(cfg)
        assert win.minimumWidth() == 900
        assert win.minimumHeight() == 600
        assert win.width() >= 900
        assert win.height() >= 600
        assert win.windowFlags() & Qt.FramelessWindowHint

