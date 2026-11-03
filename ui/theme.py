"""
FaceLock macOS Ventura / Sonoma Design Tokens & Styling
Single source of truth for all colors, typography, metrics, and QSS rules.
Complies with WCAG AA 4.5:1 minimum contrast ratio for text.
"""
import platform
import logging
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QApplication, QLabel

logger = logging.getLogger("facelock.theme")
IS_WINDOWS = platform.system() == "Windows"


def is_system_dark_mode() -> bool:
    """Detects whether the operating system is in dark mode."""
    if IS_WINDOWS:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return val == 0
        except Exception:
            return False  # Default to light
    return False


def clear_label_backplates(root) -> None:
    """Force text labels to paint without the Windows palette backplate.

    Per-widget Qt stylesheets take precedence over application-level QLabel
    rules. Preserve labels that intentionally declare their own background
    (pills/badges), and explicitly clear it for all other labels.
    """
    for label in root.findChildren(QLabel):
        label.setAutoFillBackground(False)
        label.setAttribute(Qt.WA_StyledBackground, True)
        stylesheet = label.styleSheet()
        if "background-color" not in stylesheet and "background:" not in stylesheet:
            label.setStyleSheet(stylesheet + "\nbackground-color: transparent; border: none;")


class ThemeTokens:
    """
    Design tokens matching macOS Sonoma System Settings.
    """
    def __init__(self, mode: str = "light"):
        self.is_dark = mode == "dark"

        if not self.is_dark:
            # Light mode tokens (exact specification)
            self.window_bg = "#F5F5F7"
            self.sidebar_bg = "#ECECF0"
            self.sidebar_border = "#DCDCE2"
            self.card_bg = "#FFFFFF"
            self.card_border = "#E4E4E8"
            self.row_divider = "#EDEDF0"
            self.control_border = "#CFCFD6"
            self.text_primary = "#1D1D1F"
            self.text_secondary = "#5C5C63"  # Minimum 4.5:1 on #FFFFFF and #F5F5F7

            self.accent = "#0066D6"
            self.accent_soft = "#D5E5FA"
            self.accent_text_on_soft = "#0B4FA8"

            self.success = "#1B7F45"
            self.success_bg = "#E4F4EA"
            self.danger = "#C4001A"
            self.danger_bg = "#FDE8EA"
            self.warning = "#8A5300"
            self.warning_bg = "#FFF1DC"

            self.danger_outline = "#E8B4BB"
            self.toggle_off = "#8E8E93"
            self.segmented_track = "#E6E6EA"

            self.info_banner_bg = "#E6F0FC"
            self.info_banner_text = "#0B3F8A"
            self.preview_dark = "#2C2C30"

            self.traffic_red = "#FF5F57"
            self.traffic_yellow = "#FEBC2E"
            self.traffic_green = "#28C840"

            self.nav_hover_bg = "rgba(0, 0, 0, 0.04)"
            self.focus_ring = "#0066D6"
        else:
            # Derived dark mode tokens with >= 4.5:1 contrast
            self.window_bg = "#1C1C1E"
            self.sidebar_bg = "#242426"
            self.sidebar_border = "#38383C"
            self.card_bg = "#2C2C2E"
            self.card_border = "#3A3A3C"
            self.row_divider = "#38383A"
            self.control_border = "#48484A"
            self.text_primary = "#F5F5F7"
            self.text_secondary = "#A1A1A6"  # >= 5.2:1 contrast against #2C2C2E

            self.accent = "#0A84FF"
            self.accent_soft = "#1A3A60"
            self.accent_text_on_soft = "#70B1FF"

            self.success = "#30D158"
            self.success_bg = "#143820"
            self.danger = "#FF453A"
            self.danger_bg = "#3C1418"
            self.warning = "#FF9F0A"
            self.warning_bg = "#3D290A"

            self.danger_outline = "#6E2028"
            self.toggle_off = "#636366"
            self.segmented_track = "#3A3A3C"

            self.info_banner_bg = "#1B2A40"
            self.info_banner_text = "#82B6FF"
            self.preview_dark = "#18181A"

            self.traffic_red = "#FF5F57"
            self.traffic_yellow = "#FEBC2E"
            self.traffic_green = "#28C840"

            self.nav_hover_bg = "rgba(255, 255, 255, 0.06)"
            self.focus_ring = "#0A84FF"

        # Radii
        self.radius_window = 12
        self.radius_hero_card = 16
        self.radius_card = 12
        self.radius_segmented = 9
        self.radius_segmented_inner = 7
        self.radius_toggle = 13

        # Spacing
        self.spacing_grid = 8
        self.page_padding_v = 28
        self.page_padding_h = 32
        self.block_gap = 16
        self.card_padding = 16

    @staticmethod
    def get_font(
        size_pt: int = 13,
        weight: int = QFont.Weight.Normal,
        tabular: bool = False
    ) -> QFont:
        """
        Returns Inter font with fallback to Segoe UI, -apple-system, sans-serif.
        Configures tabular numbers when requested for counters, scores, or timers.
        """
        font = QFont()
        font.setFamilies(["Inter", "Segoe UI", "-apple-system", "sans-serif"])
        font.setPointSize(size_pt)
        if isinstance(weight, int):
            weight_map = {
                400: QFont.Weight.Normal,
                500: QFont.Weight.Medium,
                600: QFont.Weight.DemiBold,
                700: QFont.Weight.Bold,
                800: QFont.Weight.ExtraBold,
            }
            font.setWeight(weight_map.get(weight, QFont.Weight.Normal))
        else:
            font.setWeight(weight)

        if tabular:
            font.setStyleHint(QFont.Monospace)
        return font

    def get_stylesheet(self) -> str:
        """Global application stylesheet with focus rings and scrollbar styling."""
        font_family = '"Inter", "Segoe UI", -apple-system, sans-serif'
        return f"""
        QWidget {{
            font-family: {font_family};
            color: {self.text_primary};
            font-size: 13px;
            outline: none;
        }}
        QLabel {{
            background-color: rgba(0, 0, 0, 0);
            border: 0px;
        }}
        QWidget:focus {{
            outline: 2px solid {self.focus_ring};
            outline-offset: 2px;
        }}
        QMainWindow {{
            background-color: {self.window_bg};
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 7px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {self.control_border};
            min-height: 20px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {self.text_secondary};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QToolTip {{
            background-color: {self.card_bg};
            color: {self.text_primary};
            border: 1px solid {self.card_border};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
        }}
        """
