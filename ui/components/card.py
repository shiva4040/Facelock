"""
FaceLock macOS Settings Inset Card & Row Components
Provides Sonoma styled grouped inset containers with subtle hairline borders,
12px / 16px radius, and inset row dividers.
"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from ui.theme import ThemeTokens


class MacCard(QFrame):
    """
    macOS Sonoma grouped inset card.
    Standard: radius 12px, padding 14-16px.
    Hero variant: radius 16px, padding 22-24px.
    """
    def __init__(self, is_hero: bool = False, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.is_hero = is_hero
        self.is_dark = is_dark
        self.setObjectName("MacCard")
        self._apply_style()

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._apply_style()

    def _apply_style(self):
        bg = "#2C2C2E" if self.is_dark else "#FFFFFF"
        border = "#3A3A3C" if self.is_dark else "#E4E4E8"
        radius = 16 if self.is_hero else 12

        self.setStyleSheet(f"""
            QFrame#MacCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: {radius}px;
            }}
        """)


class SettingsRow(QWidget):
    """
    Standard macOS System Settings row item:
    Left: Title (13px medium) + optional Subtitle (11px secondary)
    Right: Interactive control
    Bottom: Inset Divider line (#EDEDF0 light / #38383A dark)
    """
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        widget: QWidget = None,
        has_divider: bool = True,
        is_dark: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.has_divider = has_divider
        self.is_dark = is_dark
        self.setFixedHeight(56 if subtitle else 44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(12)

        # Text stack
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        title_color = "#F5F5F7" if is_dark else "#1D1D1F"
        subtitle_color = "#A1A1A6" if is_dark else "#5C5C63"

        self.title_label = QLabel(title, self)
        self.title_label.setFont(ThemeTokens.get_font(size_pt=13, weight=500))
        self.title_label.setStyleSheet(f"color: {title_color};")
        text_layout.addWidget(self.title_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setFont(ThemeTokens.get_font(size_pt=11))
            self.subtitle_label.setStyleSheet(f"color: {subtitle_color};")
            text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout)
        layout.addStretch()

        if widget:
            layout.addWidget(widget, 0, Qt.AlignVCenter)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.has_divider:
            painter = QPainter(self)
            divider_color = QColor("#38383A" if self.is_dark else "#EDEDF0")
            painter.setPen(QPen(divider_color, 1.0))
            y = self.height() - 1
            painter.drawLine(16, y, self.width() - 16, y)
            painter.end()
