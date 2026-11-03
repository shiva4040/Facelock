"""
FaceLock macOS Sonoma Toggle Switch
Size: 42x26 px, on: #1B7F45, off: #8E8E93, 22px white thumb with drop shadow.
Smooth 200ms ease-out slide animation. Full accessibility and keyboard focus support.
"""
from PySide6.QtCore import Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QKeyEvent
from PySide6.QtWidgets import QWidget


class MacToggle(QWidget):
    toggled = Signal(bool)

    def __init__(
        self,
        checked: bool = False,
        active_color: str = "#1B7F45",
        accessible_name: str = "Toggle switch",
        parent=None
    ):
        super().__init__(parent)
        self.setFixedSize(42, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self._checked = checked
        self._thumb_position = 18.0 if checked else 2.0

        # Colors from design spec
        self._on_color = QColor(active_color or "#1B7F45")
        self._off_color = QColor("#8E8E93")
        self._focus_color = QColor("#0066D6")

        self.setAccessibleName(accessible_name)
        self._update_accessibility()

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _update_accessibility(self):
        self.setAccessibleDescription("checked" if self._checked else "unchecked")

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._start_animation()
            self._update_accessibility()
            self.toggled.emit(self._checked)
            self.update()

    def setCheckedQuietly(self, checked: bool):
        """Updates visual state without emitting toggled signal."""
        if self._checked != checked:
            self._checked = checked
            self._start_animation()
            self._update_accessibility()
            self.update()

    def _get_thumb_pos(self) -> float:
        return self._thumb_position

    def _set_thumb_pos(self, pos: float):
        self._thumb_position = pos
        self.update()

    thumb_position = Property(float, _get_thumb_pos, _set_thumb_pos)

    def _start_animation(self):
        self._anim.stop()
        self._anim.setStartValue(self._thumb_position)
        self._anim.setEndValue(18.0 if self._checked else 2.0)
        self._anim.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Space, Qt.Key_Return):
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        radius = 13.0  # exactly h / 2

        # Focus ring
        if self.hasFocus():
            painter.setPen(QPen(self._focus_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # Track
        bg_color = self._on_color if self._checked else self._off_color
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # Thumb shadow (soft macOS drop shadow)
        thumb_diam = 22.0
        thumb_x = self._thumb_position
        thumb_y = 2.0

        painter.setBrush(QColor(0, 0, 0, 35))
        painter.drawEllipse(QRectF(thumb_x, thumb_y + 1.2, thumb_diam, thumb_diam))

        # Thumb knob
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_diam, thumb_diam))

        painter.end()
