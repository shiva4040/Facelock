"""
FaceLock macOS Sonoma Badge / Pill Component
11px semibold text with rounded pill background.
Variants: beta, locked, cancelled, info, score, custom.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from ui.theme import ThemeTokens


class Badge(QLabel):
    def __init__(
        self,
        text: str = "",
        variant: str = "beta",
        is_dark: bool = False,
        parent=None
    ):
        super().__init__(text, parent)
        self.variant = variant
        self.is_dark = is_dark
        self.setAlignment(Qt.AlignCenter)
        self.setFont(ThemeTokens.get_font(size_pt=11, weight=600))
        self._apply_style()

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._apply_style()

    def _apply_style(self):
        if self.variant == "beta":
            bg = "#3D290A" if self.is_dark else "#FFF1DC"
            fg = "#FF9F0A" if self.is_dark else "#8A5300"
            border = "none"
        elif self.variant == "locked":
            bg = "#3C1418" if self.is_dark else "#FDE8EA"
            fg = "#FF453A" if self.is_dark else "#C4001A"
            border = "none"
        elif self.variant == "cancelled":
            bg = "#3D290A" if self.is_dark else "#FFF1DC"
            fg = "#FF9F0A" if self.is_dark else "#8A5300"
            border = "none"
        elif self.variant == "score":
            bg = "#18181A" if self.is_dark else "#2C2C30"
            fg = "#FFFFFF"
            border = "none"
        elif self.variant == "info":
            bg = "#1A3A60" if self.is_dark else "#D5E5FA"
            fg = "#70B1FF" if self.is_dark else "#0B4FA8"
            border = "none"
        else:
            bg = "#3A3A3C" if self.is_dark else "#E6E6EA"
            fg = "#F5F5F7" if self.is_dark else "#1D1D1F"
            border = "none"

        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: {border};
                border-radius: 9px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)

