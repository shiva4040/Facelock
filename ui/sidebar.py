"""
FaceLock macOS Sonoma Sidebar
Width: 220px fixed.
Features:
- Traffic lights (Red #FF5F57, Yellow #FEBC2E, Green #28C840) centered at x=22, y=22
- 30px blue rounded app badge with white shield-check + "FaceLock" 15px semibold
- Nav items (34px high, 8px radius, 18px line icons, 1.75 stroke):
  Dashboard, Owner Face, Security, Activity
- Active item: bg #D5E5FA, text #0B4FA8, semibold (light) / bg #1A3A60, text #70B1FF (dark)
- Inactive item: text #1D1D1F (light) / #F5F5F7 (dark), hover rgba(0,0,0,0.04)
- Footer: 11px secondary text (#5C5C63):
  "Runs on this device only."
  "Nothing is uploaded. Version 1.0"
- Right border hairline: #DCDCE2 (light) / #38383C (dark)
- Rounded window corners (radius 12px) on top-left and bottom-left
"""
from typing import List, Tuple
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from ui.components.traffic_lights import TrafficLights
from ui.theme import ThemeTokens
from ui.strings import Strings


def render_sidebar_icon(name: str, color: QColor, size: int = 18) -> QPixmap:
    """Renders 18x18 Lucide-style line vector icons with 1.75 stroke width."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, 1.75, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if name == "dashboard":
        # 2x2 Grid (Lucide LayoutGrid)
        s = 6.0
        painter.drawRoundedRect(QRectF(1.5, 1.5, s, s), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(10.5, 1.5, s, s), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(1.5, 10.5, s, s), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(10.5, 10.5, s, s), 1.5, 1.5)

    elif name == "owner_face":
        # Scan Face / Viewfinder corners around face oval
        # Top-left corner
        painter.drawLine(2, 6, 2, 3)
        painter.drawLine(2, 3, 5, 3)
        # Top-right corner
        painter.drawLine(13, 3, 16, 3)
        painter.drawLine(16, 3, 16, 6)
        # Bottom-left corner
        painter.drawLine(2, 12, 2, 15)
        painter.drawLine(2, 15, 5, 15)
        # Bottom-right corner
        painter.drawLine(13, 15, 16, 15)
        painter.drawLine(16, 15, 16, 12)
        # Center face head oval
        painter.drawEllipse(QRectF(5.5, 5.0, 7.0, 8.0))

    elif name == "security":
        # Sliders / Tune (Lucide SlidersHorizontal)
        # Top slider track
        painter.drawLine(2, 6, 16, 6)
        painter.drawEllipse(QRectF(5, 4, 4, 4))
        # Bottom slider track
        painter.drawLine(2, 12, 16, 12)
        painter.drawEllipse(QRectF(10, 10, 4, 4))

    elif name == "activity":
        # Clock (Lucide History/Clock)
        painter.drawEllipse(QRectF(2, 2, 14, 14))
        painter.drawLine(9, 5, 9, 9)
        painter.drawLine(9, 9, 12, 9)

    elif name == "settings":
        # Gear (Lucide Settings)
        painter.drawEllipse(QRectF(5.5, 5.5, 7, 7))
        for a in (0, 60, 120, 180, 240, 300):
            painter.save()
            painter.translate(9, 9)
            painter.rotate(a)
            painter.drawLine(0, -6.5, 0, -8.5)
            painter.restore()

    painter.end()
    return pm


def render_app_badge(size: int = 30) -> QPixmap:
    """Renders the 30px blue rounded square with crisp white shield-check."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # Rounded blue background
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(QColor("#0066D6")))
    painter.drawRoundedRect(QRectF(0, 0, size, size), 7.0, 7.0)

    # White shield with check
    painter.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)

    cx = size / 2.0
    cy = size / 2.0
    painter.translate(cx, cy)

    # Shield outline
    shield = QPainterPath()
    shield.moveTo(0, -7.5)
    shield.lineTo(6.5, -4.5)
    shield.lineTo(6.5, 1.5)
    shield.cubicTo(6.5, 5.5, 0, 8.5, 0, 8.5)
    shield.cubicTo(0, 8.5, -6.5, 5.5, -6.5, 1.5)
    shield.lineTo(-6.5, -4.5)
    shield.closeSubpath()
    painter.drawPath(shield)

    # Checkmark inside shield
    check = QPainterPath()
    check.moveTo(-3, 0.5)
    check.lineTo(-0.8, 2.8)
    check.lineTo(3.2, -1.8)
    painter.drawPath(check)

    painter.end()
    return pm


class SidebarButton(QPushButton):
    def __init__(self, key: str, label: str, index: int, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.key = key
        self.label = label
        self.index = index
        self.is_dark = is_dark
        self._active = False
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(label)
        self._update_appearance()

    def set_active(self, active: bool):
        self._active = active
        self._update_appearance()

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._update_appearance()

    def _update_appearance(self):
        if not self.is_dark:
            active_bg = "#D5E5FA"
            active_fg = "#0B4FA8"
            inactive_fg = "#1D1D1F"
            hover_bg = "rgba(0, 0, 0, 0.04)"
            focus_ring = "#0066D6"
        else:
            active_bg = "#1A3A60"
            active_fg = "#70B1FF"
            inactive_fg = "#F5F5F7"
            hover_bg = "rgba(255, 255, 255, 0.06)"
            focus_ring = "#0A84FF"

        bg = active_bg if self._active else "transparent"
        fg = active_fg if self._active else inactive_fg
        weight = "600" if self._active else "500"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-radius: 8px;
                padding-left: 36px;
                text-align: left;
                font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
                font-size: 13px;
                font-weight: {weight};
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {active_bg if self._active else hover_bg};
            }}
            QPushButton:focus {{
                border: 2px solid {focus_ring};
            }}
        """)
        self.setText(self.label)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.is_dark:
            color = QColor("#0B4FA8") if self._active else QColor("#5C5C63")
        else:
            color = QColor("#70B1FF") if self._active else QColor("#A1A1A6")

        icon_pm = render_sidebar_icon(self.key, color, size=18)
        y = (self.height() - 18) // 2
        painter.drawPixmap(10, y, icon_pm)
        painter.end()


class Sidebar(QWidget):
    page_changed = Signal(int)
    close_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()

    NAV_ITEMS = [
        ("dashboard", Strings.NAV_DASHBOARD),
        ("owner_face", Strings.NAV_OWNER_FACE),
        ("security", Strings.NAV_SECURITY),
        ("activity", Strings.NAV_ACTIVITY),
    ]

    def __init__(self, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.is_dark = is_dark
        self._buttons: List[SidebarButton] = []
        self._current_index = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 18)
        layout.setSpacing(4)

        # 1. Traffic lights (red, yellow, green)
        self.traffic_lights = TrafficLights(self)
        self.traffic_lights.close_clicked.connect(self.close_clicked)
        self.traffic_lights.minimize_clicked.connect(self.minimize_clicked)
        self.traffic_lights.maximize_clicked.connect(self.maximize_clicked)
        layout.addWidget(self.traffic_lights)

        layout.addSpacing(12)

        # 2. App Badge + Title row ("FaceLock" 15px semibold)
        app_header = QWidget(self)
        header_layout = QHBoxLayout(app_header)
        header_layout.setContentsMargins(4, 0, 4, 0)
        header_layout.setSpacing(10)

        badge_label = QLabel(app_header)
        badge_label.setPixmap(render_app_badge(30))
        badge_label.setFixedSize(30, 30)
        header_layout.addWidget(badge_label)

        title_label = QLabel(Strings.APP_NAME, app_header)
        title_label.setFont(ThemeTokens.get_font(size_pt=15, weight=600))
        title_color = "#F5F5F7" if self.is_dark else "#1D1D1F"
        title_label.setStyleSheet(f"color: {title_color};")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addWidget(app_header)
        layout.addSpacing(14)

        # 3. Nav items (34px high, 8px radius, 18px line icons, 1.75 stroke)
        for idx, (key, label) in enumerate(self.NAV_ITEMS):
            btn = SidebarButton(key, label, idx, is_dark=self.is_dark, parent=self)
            btn.clicked.connect(lambda checked=False, i=idx: self.select_page(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Settings is a secondary destination: keep it at the bottom of the
        # navigation, separate from the four primary screens in the mockups.
        self.settings_button = SidebarButton(
            "settings", Strings.NAV_SETTINGS, len(self.NAV_ITEMS),
            is_dark=self.is_dark, parent=self
        )
        self.settings_button.clicked.connect(
            lambda checked=False: self.select_page(self.settings_button.index)
        )
        layout.addWidget(self.settings_button)

        # 4. Sidebar footer (11px secondary text)
        footer_widget = QWidget(self)
        footer_layout = QVBoxLayout(footer_widget)
        footer_layout.setContentsMargins(6, 0, 6, 0)
        footer_layout.setSpacing(2)

        footer_color = "#A1A1A6" if self.is_dark else "#5C5C63"

        f1 = QLabel(Strings.SIDEBAR_FOOTER_LINE1, footer_widget)
        f1.setFont(ThemeTokens.get_font(size_pt=11))
        f1.setStyleSheet(f"color: {footer_color};")
        footer_layout.addWidget(f1)

        f2 = QLabel(Strings.SIDEBAR_FOOTER_LINE2, footer_widget)
        f2.setFont(ThemeTokens.get_font(size_pt=11))
        f2.setStyleSheet(f"color: {footer_color};")
        footer_layout.addWidget(f2)

        layout.addWidget(footer_widget)

        self.select_page(0)

    def select_page(self, index: int):
        self._current_index = index
        for idx, btn in enumerate(self._buttons):
            btn.set_active(idx == index)
        self.settings_button.set_active(index == self.settings_button.index)
        self.page_changed.emit(index)

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        for btn in self._buttons:
            btn.setDarkTheme(is_dark)
        self.settings_button.setDarkTheme(is_dark)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = 12.0

        # Rounded sidebar clip for left side of window
        path = QPainterPath()
        path.moveTo(w, 0)
        path.lineTo(radius, 0)
        path.arcTo(0, 0, radius * 2, radius * 2, 90, 90)
        path.lineTo(0, h - radius)
        path.arcTo(0, h - radius * 2, radius * 2, radius * 2, 180, 90)
        path.lineTo(w, h)
        path.closeSubpath()

        bg = QColor("#242426" if self.is_dark else "#ECECF0")
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawPath(path)

        # Right hairline border (#DCDCE2 light / #38383C dark)
        border_col = QColor("#38383C" if self.is_dark else "#DCDCE2")
        painter.setPen(QPen(border_col, 1.0))
        x = w - 1
        painter.drawLine(int(x), 0, int(x), int(h))
        painter.end()
