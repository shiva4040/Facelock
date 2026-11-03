"""
macOS Traffic Light Window Control Buttons
Red (Close), Yellow (Minimize), Green (Maximize) with subtle hover symbols.
"""
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget


class TrafficLights(QWidget):
    close_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(68, 20)
        self.setMouseTracking(True)
        self._hovered = False
        self._hover_btn = None  # "close", "min", "max"

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._hover_btn = None
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if QRect(4, 4, 12, 12).contains(pos):
            self._hover_btn = "close"
        elif QRect(24, 4, 12, 12).contains(pos):
            self._hover_btn = "min"
        elif QRect(44, 4, 12, 12).contains(pos):
            self._hover_btn = "max"
        else:
            self._hover_btn = None
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if QRect(4, 4, 12, 12).contains(pos):
                self.close_clicked.emit()
            elif QRect(24, 4, 12, 12).contains(pos):
                self.minimize_clicked.emit()
            elif QRect(44, 4, 12, 12).contains(pos):
                self.maximize_clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Colors matching exact specification
        c_red = QColor("#FF5F57")
        c_yellow = QColor("#FEBC2E")
        c_green = QColor("#28C840")

        b_red = QColor(224, 68, 62)
        b_yellow = QColor(222, 161, 35)
        b_green = QColor(26, 171, 41)

        symbol_pen = QPen(QColor(70, 20, 20, 180), 1.2)

        # Close
        painter.setPen(QPen(b_red, 0.8))
        painter.setBrush(QBrush(c_red))
        painter.drawEllipse(4, 4, 12, 12)
        if self._hovered:
            painter.setPen(symbol_pen)
            painter.drawLine(8, 8, 12, 12)
            painter.drawLine(12, 8, 8, 12)

        # Minimize
        painter.setPen(QPen(b_yellow, 0.8))
        painter.setBrush(QBrush(c_yellow))
        painter.drawEllipse(24, 4, 12, 12)
        if self._hovered:
            painter.setPen(QPen(QColor(90, 60, 10, 180), 1.4))
            painter.drawLine(27, 10, 33, 10)

        # Maximize / Zoom
        painter.setPen(QPen(b_green, 0.8))
        painter.setBrush(QBrush(c_green))
        painter.drawEllipse(44, 4, 12, 12)
        if self._hovered:
            painter.setPen(QPen(QColor(10, 60, 20, 180), 1.2))
            painter.drawLine(48, 8, 52, 12)
            painter.drawLine(52, 8, 48, 12)

        painter.end()

