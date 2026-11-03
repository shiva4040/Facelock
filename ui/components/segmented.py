"""
FaceLock macOS Sonoma Segmented Control
Outer track: #E6E6EA (light) / #3A3A3C (dark), 2px padding, radius 9px.
Active segment: white #FFFFFF (light) with subtle drop shadow, radius 7px, semibold text.
Full keyboard arrow navigation and accessibility support.
"""
from typing import List
from PySide6.QtCore import Qt, Signal, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QKeyEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup

from ui.theme import ThemeTokens


class SegmentedControl(QWidget):
    currentChanged = Signal(int)
    currentTextChanged = Signal(str)

    def __init__(self, items: List[str], default_index: int = 0, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.items = items
        self._current_index = default_index if 0 <= default_index < len(items) else 0
        self.is_dark = is_dark
        self.setFixedHeight(32)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

        self._track_color = QColor("#3A3A3C" if is_dark else "#E6E6EA")
        self._active_bg = QColor("#636366" if is_dark else "#FFFFFF")
        self._active_text = QColor("#FFFFFF" if is_dark else "#1D1D1F")
        self._inactive_text = QColor("#A1A1A6" if is_dark else "#5C5C63")
        self._focus_color = QColor("#0A84FF" if is_dark else "#0066D6")

        self.setAccessibleName("Segmented selector")
        self._update_accessibility()

    def _update_accessibility(self):
        if 0 <= self._current_index < len(self.items):
            self.setAccessibleDescription(f"Selected: {self.items[self._current_index]}")

    def currentIndex(self) -> int:
        return self._current_index

    def currentText(self) -> str:
        if 0 <= self._current_index < len(self.items):
            return self.items[self._current_index]
        return ""

    def setCurrentIndex(self, index: int):
        if 0 <= index < len(self.items) and index != self._current_index:
            self._current_index = index
            self._update_accessibility()
            self.update()
            self.currentChanged.emit(self._current_index)
            self.currentTextChanged.emit(self.items[self._current_index])

    def setCurrentText(self, text: str):
        if text in self.items:
            self.setCurrentIndex(self.items.index(text))

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self._track_color = QColor("#3A3A3C" if is_dark else "#E6E6EA")
        self._active_bg = QColor("#636366" if is_dark else "#FFFFFF")
        self._active_text = QColor("#FFFFFF" if is_dark else "#1D1D1F")
        self._inactive_text = QColor("#A1A1A6" if is_dark else "#5C5C63")
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            count = len(self.items)
            if count > 0:
                seg_width = self.width() / count
                clicked_idx = int(event.position().x() / seg_width)
                if 0 <= clicked_idx < count:
                    self.setCurrentIndex(clicked_idx)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Left:
            if self._current_index > 0:
                self.setCurrentIndex(self._current_index - 1)
                event.accept()
        elif event.key() == Qt.Key_Right:
            if self._current_index < len(self.items) - 1:
                self.setCurrentIndex(self._current_index + 1)
                event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        count = len(self.items)
        if count == 0:
            return

        # Track outer
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 9.0, 9.0)

        # Focus ring
        if self.hasFocus():
            painter.setPen(QPen(self._focus_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 9.0, 9.0)

        seg_w = (w - 4.0) / count
        seg_h = h - 4.0
        active_x = 2.0 + self._current_index * seg_w

        # Active segment drop shadow
        if not self.is_dark:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 15))
            painter.drawRoundedRect(QRectF(active_x, 2.0 + 1.0, seg_w, seg_h), 7.0, 7.0)

        # Active segment pill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._active_bg))
        painter.drawRoundedRect(QRectF(active_x, 2.0, seg_w, seg_h), 7.0, 7.0)

        # Draw segment texts
        for i, text in enumerate(self.items):
            item_x = 2.0 + i * seg_w
            is_active = (i == self._current_index)

            font = ThemeTokens.get_font(
                size_pt=12,
                weight=QFont.DemiBold if is_active else QFont.Normal
            )
            painter.setFont(font)
            text_color = self._active_text if is_active else self._inactive_text
            painter.setPen(text_color)
            painter.drawText(
                QRectF(item_x, 2.0, seg_w, seg_h),
                Qt.AlignCenter,
                text
            )

        painter.end()

