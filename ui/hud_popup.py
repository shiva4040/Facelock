"""
FaceLock Come-in / Come-out HUD Popup
Matches macOS Sonoma design specification exactly:
- Dimensions: 280x165 px, rounded 20px, frosted white #FFFFFF, soft drop shadow.
- Centered on active display where cursor is, always on top, never steals focus.
- 48px vector icon circle:
  - Welcome back: #E4F4EA bg, #1B7F45 check
  - Owner away: #E6E6EA bg, #5C5C63 user outline
  - Unknown person: #FFF1DC bg, #8A5300 warning triangle
  - Locking in 3 s: #FDE8EA bg, #C4001A lock + Cancel button + 4px red draining progress bar.
- Auto-dismisses in 2.5s with smooth 200ms ease-out fade.
"""
import os
import sys
import time
import logging
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QRectF, Property
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QPainterPath, QCursor
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QApplication, QGraphicsOpacityEffect
)

from core.events import events
from core.config import AppConfig
from ui.theme import ThemeTokens
from ui.strings import Strings
from ui.components.pill_button import PillButton

logger = logging.getLogger("facelock.hud")


def render_hud_circle_icon(state: str, size: int = 48) -> QPixmap:
    """Renders 48px circular vector icon matching Image 5 design exactly."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    if state == "welcome":
        bg = QColor("#E4F4EA")
        fg = QColor("#1B7F45")
    elif state == "owner_left":
        bg = QColor("#E6E6EA")
        fg = QColor("#5C5C63")
    elif state == "stranger_warning":
        bg = QColor("#FFF1DC")
        fg = QColor("#8A5300")
    else:  # locking_countdown or locked
        bg = QColor("#FDE8EA")
        fg = QColor("#C4001A")

    # Background circle
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(bg))
    painter.drawEllipse(0, 0, size, size)

    # Foreground vector icon
    painter.setPen(QPen(fg, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)

    cx = size / 2.0
    cy = size / 2.0
    painter.translate(cx, cy)

    if state == "welcome":
        # Green checkmark
        path = QPainterPath()
        path.moveTo(-6, 0)
        path.lineTo(-1.5, 4.5)
        path.lineTo(7, -4)
        painter.drawPath(path)

    elif state == "owner_left":
        # User head & shoulders
        painter.drawEllipse(QRectF(-5, -9, 10, 10))
        painter.drawArc(QRectF(-9, -1, 18, 15), 30 * 16, 120 * 16)

    elif state == "stranger_warning":
        # Amber warning triangle
        tri = QPainterPath()
        tri.moveTo(0, -9)
        tri.lineTo(9.5, 7.5)
        tri.lineTo(-9.5, 7.5)
        tri.closeSubpath()
        painter.drawPath(tri)
        painter.drawLine(0, -3.5, 0, 1.5)
        painter.drawPoint(0, 5)

    else:
        # Red lock
        painter.drawRoundedRect(QRectF(-6.5, -2, 13, 11), 2, 2)
        painter.drawArc(QRectF(-4.5, -8, 9, 9), 0, 180 * 16)

    painter.end()
    return pm


render_hud_icon = render_hud_circle_icon


class HudPopup(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._current_state = "welcome"
        self._countdown_remaining = 3
        self._countdown_total = 3
        self._progress_fraction = 1.0

        self._init_window()
        self._build_ui()

        # Timers & Animations
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._start_fade_out)

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(100)  # smooth draining progress bar
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_start_time = 0.0

        # Opacity Fade Animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        # Wire global event bus
        events.hud_trigger.connect(self.trigger)

    def _init_window(self):
        # Never steals focus, stays on top, tool window
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(280, 165)

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 18, 16, 14)
        root_layout.setSpacing(6)
        root_layout.setAlignment(Qt.AlignCenter)

        # 48px Centered Vector Icon
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(self.icon_label, 0, Qt.AlignCenter)

        root_layout.addSpacing(2)

        # Title (15px semibold, #1D1D1F)
        self.title_label = QLabel(Strings.HUD_WELCOME_TITLE, self)
        self.title_label.setFont(ThemeTokens.get_font(size_pt=15, weight=600))
        self.title_label.setStyleSheet("color: #1D1D1F; background-color: transparent;")
        self.title_label.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(self.title_label, 0, Qt.AlignCenter)

        # Subtitle (12px, #5C5C63)
        self.subtitle_label = QLabel(Strings.HUD_WELCOME_SUBTITLE, self)
        self.subtitle_label.setFont(ThemeTokens.get_font(size_pt=12))
        self.subtitle_label.setStyleSheet("color: #5C5C63; background-color: transparent;")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(self.subtitle_label, 0, Qt.AlignCenter)

        # Cancel Pill Button (visible only in countdown state)
        self.cancel_btn = PillButton(Strings.HUD_BTN_CANCEL, variant="secondary", is_dark=False, parent=self)
        self.cancel_btn.setFixedSize(80, 28)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.hide()
        self.btn_container = self.cancel_btn
        root_layout.addWidget(self.cancel_btn, 0, Qt.AlignCenter)

    def trigger(self, state: str, title: str, subtitle: str, extra: Dict[str, Any] = None):
        """Displays HUD popup with appropriate state, icon, and dismiss duration."""
        if not self.config.notifications_enabled:
            return

        self._current_state = state
        self.icon_label.setPixmap(render_hud_circle_icon(state, size=48))
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)

        if state == "locking_countdown":
            self.cancel_btn.show()
            self._countdown_total = max(1, int((extra or {}).get("countdown", 3)))
            self._countdown_start_time = time.time()
            self._progress_fraction = 1.0
            self._countdown_timer.start()
            self._dismiss_timer.stop()
        else:
            self.cancel_btn.hide()
            self._countdown_timer.stop()
            self._progress_fraction = 0.0
            # Auto-dismiss after 2.5s
            self._dismiss_timer.start(2500)

        self._reposition_center_of_active_screen()
        self._start_fade_in()

    def _reposition_center_of_active_screen(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
            self.move(x, y)

    def _start_fade_in(self):
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self.show()
        self._anim.start()

    def _start_fade_out(self):
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._on_fade_out_finished)
        self._anim.start()

    def _on_fade_out_finished(self):
        try:
            self._anim.finished.disconnect(self._on_fade_out_finished)
        except Exception:
            pass
        self.hide()

    def _on_countdown_tick(self):
        elapsed = time.time() - self._countdown_start_time
        remaining = max(0.0, self._countdown_total - elapsed)
        self._progress_fraction = remaining / float(self._countdown_total)
        self.title_label.setText(Strings.HUD_LOCKING_TITLE.format(sec=max(1, int(round(remaining)))))
        self.update()

        if remaining <= 0:
            self._countdown_timer.stop()
            self._progress_fraction = 0.0
            self.update()

    def _on_cancel_clicked(self):
        self._countdown_timer.stop()
        events.hud_cancel_countdown.emit()
        self._start_fade_out()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        w = float(rect.width())
        h = float(rect.height())
        radius = 20.0

        # Rounded frosted white card with hairline border
        painter.setPen(QPen(QColor(0, 0, 0, 18), 1.0))
        painter.setBrush(QBrush(QColor(255, 255, 255, 248)))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # In countdown state: 4px red progress bar draining along bottom edge
        if self._current_state == "locking_countdown" and self._progress_fraction > 0.0:
            bar_w = (w - 8) * self._progress_fraction
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#C4001A")))
            painter.drawRoundedRect(QRectF(4, h - 6, bar_w, 4), 2, 2)

        painter.end()
