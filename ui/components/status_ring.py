"""
FaceLock macOS Hero Status Ring Component
88px status ring with center vector icon and animated stroke.
States:
- "protected": green full ring (#1B7F45), shield-check icon
- "paused": gray ring (#8E8E93), pause bars icon
- "intruder": red ring (#C4001A), warning/alert icon
- "camera_busy": amber ring (#8A5300), camera-slash icon
- "tamper": red ring (#C4001A), shield-x icon
"""
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PySide6.QtWidgets import QWidget


class StatusRing(QWidget):
    def __init__(self, size: int = 88, status: str = "protected", is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._status = status
        self.is_dark = is_dark
        self._anim_progress = 1.0

        self._anim = QPropertyAnimation(self, b"anim_progress", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _get_anim(self) -> float:
        return self._anim_progress

    def _set_anim(self, val: float):
        self._anim_progress = val
        self.update()

    anim_progress = Property(float, _get_anim, _set_anim)

    def setStatus(self, status: str):
        if status != self._status:
            self._status = status
            self._anim.stop()
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.start()

    def setDarkTheme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        thickness = 6.0
        rect = QRectF(thickness / 2.0, thickness / 2.0, w - thickness, h - thickness)

        # State color selection
        if self._status == "protected":
            color = QColor("#30D158" if self.is_dark else "#1B7F45")
        elif self._status in ("intruder", "tamper"):
            color = QColor("#FF453A" if self.is_dark else "#C4001A")
        elif self._status == "camera_busy":
            color = QColor("#FF9F0A" if self.is_dark else "#8A5300")
        else:  # paused / idle
            color = QColor("#636366" if self.is_dark else "#8E8E93")

        # Track background
        bg_track = QColor(255, 255, 255, 20) if self.is_dark else QColor(0, 0, 0, 15)
        painter.setPen(QPen(bg_track, thickness, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(rect)

        # Active animated stroke ring
        span_angle = int(-360 * 16 * self._anim_progress)
        start_angle = 90 * 16
        painter.setPen(QPen(color, thickness, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, start_angle, span_angle)

        # Draw Center Icon
        painter.save()
        cx = w / 2.0
        cy = h / 2.0
        painter.translate(cx, cy)
        scale_factor = w / 88.0
        painter.scale(scale_factor, scale_factor)

        painter.setPen(QPen(color, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)

        if self._status == "protected":
            # Shield with checkmark
            shield = QPainterPath()
            shield.moveTo(0, -18)
            shield.lineTo(14, -12)
            shield.lineTo(14, 2)
            shield.cubicTo(14, 11, 0, 18, 0, 18)
            shield.cubicTo(0, 18, -14, 11, -14, 2)
            shield.lineTo(-14, -12)
            shield.closeSubpath()
            painter.drawPath(shield)

            # Checkmark inside shield
            check = QPainterPath()
            check.moveTo(-6, 0)
            check.lineTo(-1, 5)
            check.lineTo(7, -4)
            painter.drawPath(check)

        elif self._status in ("intruder", "tamper"):
            # Shield with warning exclamation
            shield = QPainterPath()
            shield.moveTo(0, -18)
            shield.lineTo(14, -12)
            shield.lineTo(14, 2)
            shield.cubicTo(14, 11, 0, 18, 0, 18)
            shield.cubicTo(0, 18, -14, 11, -14, 2)
            shield.lineTo(-14, -12)
            shield.closeSubpath()
            painter.drawPath(shield)

            painter.drawLine(0, -6, 0, 3)
            painter.drawPoint(0, 8)

        elif self._status == "camera_busy":
            # Camera icon
            painter.drawRoundedRect(QRectF(-12, -7, 24, 16), 3, 3)
            painter.drawEllipse(QRectF(-5, -4, 10, 10))
            painter.drawLine(-14, -9, 14, 11)

        else:  # paused
            # Pause icon: two vertical bars
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(-8, -10, 5, 20), 2, 2)
            painter.drawRoundedRect(QRectF(3, -10, 5, 20), 2, 2)

        painter.restore()
        painter.end()

