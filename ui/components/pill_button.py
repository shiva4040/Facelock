"""
FaceLock macOS Sonoma Pill Button
Fully rounded button (30-34px high).
Variants:
- primary: #0066D6, white text
- secondary: white bg, 1px #CFCFD6 border, text #1D1D1F
- danger: white bg, #E8B4BB outline, #C4001A text
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from ui.theme import ThemeTokens


class PillButton(QPushButton):
    def __init__(self, text: str = "", variant: str = "primary", is_dark: bool = False, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.is_dark = is_dark
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setFocusPolicy(Qt.StrongFocus)
        self._apply_style()

    def set_variant(self, variant: str):
        self.variant = variant
        self._apply_style()

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._apply_style()

    def _apply_style(self):
        font_family = '"Inter", "Segoe UI", -apple-system, sans-serif'
        radius = 16  # fully rounded for 32px height

        if not self.is_dark:
            focus_ring = "#0066D6"
            if self.variant == "primary":
                bg = "#0066D6"
                bg_hover = "#0055B3"
                bg_pressed = "#00448F"
                text = "#FFFFFF"
                border = "none"
            elif self.variant == "danger":
                bg = "#FFFFFF"
                bg_hover = "#FDE8EA"
                bg_pressed = "#FCD5DA"
                text = "#C4001A"
                border = "1px solid #E8B4BB"
            else:  # secondary
                bg = "#FFFFFF"
                bg_hover = "#F5F5F7"
                bg_pressed = "#EBEBED"
                text = "#1D1D1F"
                border = "1px solid #CFCFD6"
        else:
            focus_ring = "#0A84FF"
            if self.variant == "primary":
                bg = "#0A84FF"
                bg_hover = "#0071E3"
                bg_pressed = "#005BB5"
                text = "#FFFFFF"
                border = "none"
            elif self.variant == "danger":
                bg = "#2C2C2E"
                bg_hover = "#3C1418"
                bg_pressed = "#4A181E"
                text = "#FF453A"
                border = "1px solid #6E2028"
            else:  # secondary
                bg = "#2C2C2E"
                bg_hover = "#3A3A3C"
                bg_pressed = "#48484A"
                text = "#F5F5F7"
                border = "1px solid #48484A"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: {border};
                border-radius: {radius}px;
                padding: 0 16px;
                font-family: {font_family};
                font-size: 13px;
                font-weight: 500;
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg_pressed};
            }}
            QPushButton:focus {{
                border: 2px solid {focus_ring};
            }}
            QPushButton:disabled {{
                background-color: {"#EAEAEA" if not self.is_dark else "#222224"};
                color: {"#A0A0A5" if not self.is_dark else "#636366"};
                border: none;
            }}
        """)
