"""Persistent, glanceable FaceLock activity strip inspired by Apple HIG."""
import time

from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QHBoxLayout, QVBoxLayout, QToolButton

from core.config import AppConfig
from core.events import events
from ui.hud_popup import render_hud_circle_icon
from ui.theme import ThemeTokens, clear_label_backplates


class LiveActivityBar(QFrame):
    """An in-app activity that stays visible and updates instead of popping up."""

    def __init__(self, config: AppConfig, on_open_activity=None, parent=None, floating=False):
        super().__init__(parent)
        self.config = config
        self.on_open_activity = on_open_activity
        self.floating = floating
        self._main_window_visible = True
        self._monitoring_active = bool(config.protection_enabled)
        self._event_active = False
        self._activity_geometry = None
        self._state = "active" if config.protection_enabled else "paused"
        self._progress = 0.0
        self._countdown_total = 0
        self._countdown_started = 0.0
        self._expanded = False
        self._last_update = time.time()

        self.setObjectName("LiveActivityBar")
        self.setFixedHeight(62)
        self.setMaximumWidth(560)
        if self.floating:
            self.setWindowFlags(
                Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                Qt.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.setWindowTitle("FaceLock Live Activity")
            self.resize(480, 62)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()

        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(100)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._dismiss_floating_activity)
        self._geometry_animation = QPropertyAnimation(self, b"geometry", self)
        self._apply_state(self._state, self._default_copy(self._state))

        events.status_changed.connect(self._on_status_changed)
        events.hud_trigger.connect(self._on_activity_event)
        events.config_updated.connect(self._on_config_updated)
        events.window_visibility_changed.connect(self._on_owner_window_visibility)
        self._on_config_updated()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 8, 12, 8)
        outer.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(11)

        self.icon = QLabel(self)
        self.icon.setFixedSize(30, 30)
        self.icon.setAlignment(Qt.AlignCenter)
        row.addWidget(self.icon)

        labels = QVBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.setSpacing(1)
        self.title = QLabel(self)
        self.title.setFont(ThemeTokens.get_font(size_pt=13, weight=600))
        self.title.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        self.subtitle = QLabel(self)
        self.subtitle.setFont(ThemeTokens.get_font(size_pt=10, weight=500))
        self.subtitle.setStyleSheet("color: #B9C0CB; background-color: transparent;")
        labels.addWidget(self.title)
        labels.addWidget(self.subtitle)
        row.addLayout(labels, 1)

        self.live_mark = QLabel("●  LIVE", self)
        self.live_mark.setFont(ThemeTokens.get_font(size_pt=9, weight=700))
        self.live_mark.setStyleSheet("color: #66D995; background-color: transparent;")
        row.addWidget(self.live_mark)

        self.cancel_button = QToolButton(self)
        self.cancel_button.setText("Cancel")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setStyleSheet(
            "QToolButton { color: #FFFFFF; background: rgba(255,255,255,30); "
            "border: 1px solid rgba(255,255,255,55); border-radius: 12px; "
            "padding: 5px 12px; font-weight: 600; } "
            "QToolButton:hover { background: rgba(255,255,255,55); }"
        )
        self.cancel_button.clicked.connect(self._cancel_countdown)
        self.cancel_button.hide()
        row.addWidget(self.cancel_button)

        self.open_window_button = QToolButton(self)
        self.open_window_button.setText("Open")
        self.open_window_button.setCursor(Qt.PointingHandCursor)
        self.open_window_button.setStyleSheet(
            "QToolButton { color: #FFFFFF; background: rgba(255,255,255,30); "
            "border: 1px solid rgba(255,255,255,55); border-radius: 12px; "
            "padding: 5px 10px; font-weight: 600; } "
            "QToolButton:hover { background: rgba(255,255,255,55); }"
        )
        self.open_window_button.clicked.connect(self._open_activity)
        self.open_window_button.setVisible(self.floating)
        row.addWidget(self.open_window_button)

        self.expand_button = QToolButton(self)
        self.expand_button.setText("⌄")
        self.expand_button.setAccessibleName("Expand live activity details")
        self.expand_button.setCursor(Qt.PointingHandCursor)
        self.expand_button.setStyleSheet(
            "QToolButton { color: #D5DCE6; background: transparent; border: none; "
            "font-size: 17px; padding: 2px 4px; }"
        )
        self.expand_button.clicked.connect(self._toggle_expanded)
        row.addWidget(self.expand_button)
        outer.addLayout(row)

        self.detail_row = QHBoxLayout()
        self.detail_row.setContentsMargins(41, 0, 2, 0)
        self.details = QLabel(self)
        self.details.setFont(ThemeTokens.get_font(size_pt=9))
        self.details.setStyleSheet("color: #AAB3C1; background-color: transparent;")
        self.detail_row.addWidget(self.details, 1)
        self.open_button = QToolButton(self)
        self.open_button.setText("View Activity  ↗")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.setStyleSheet(
            "QToolButton { color: #A8C7FF; background: transparent; border: none; "
            "font-weight: 600; } QToolButton:hover { color: #FFFFFF; }"
        )
        self.open_button.clicked.connect(self._open_activity)
        self.detail_row.addWidget(self.open_button)
        outer.addLayout(self.detail_row)
        self.details.hide()
        self.open_button.hide()

        clear_label_backplates(self)

    def _default_copy(self, state):
        if state == "paused":
            return ("paused", "Protection paused", "Turn protection on to resume live checks")
        return ("active", "Protection active", "FaceLock will keep this activity updated")

    def _apply_state(self, state: str, copy, extra=None):
        self._state = state
        self._monitoring_active = state not in ("paused", "camera_busy")
        title, subtitle = copy[1], copy[2]
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.details.setText(subtitle)
        icon_state = "welcome" if state == "active" else "owner_left" if state in ("paused", "camera_busy") else state
        self.icon.setPixmap(render_hud_circle_icon(icon_state, size=30))

        active = state not in ("paused", "camera_busy")
        self.live_mark.setText("●  LIVE" if active else "●  PAUSED")
        self.live_mark.setStyleSheet(
            f"color: {'#66D995' if active else '#B6BBC4'}; background-color: transparent;"
        )
        self.cancel_button.setVisible(state == "locking_countdown")

        if state == "locking_countdown":
            self._countdown_total = max(1, int((extra or {}).get("countdown", 3)))
            self._countdown_started = time.time()
            self._progress = 1.0
            self._countdown_timer.start()
        else:
            self._countdown_timer.stop()
            self._progress = 0.0
        self._last_update = time.time()
        self.update()
        self._sync_floating_visibility()

    def _on_activity_event(self, state, title, subtitle, extra=None):
        # Use concise, privacy-conscious copy in the glanceable presentation.
        copy = {
            "welcome": ("welcome", "Face check complete", "Protection remains active"),
            "owner_left": ("owner_left", "Area clear", "Monitoring continues in the background"),
            "stranger_warning": ("stranger_warning", "Security alert", "An unrecognized person was detected"),
            "locking_countdown": ("locking_countdown", "Locking in 3 s", "Review the alert or cancel the lock"),
            "locked": ("locked", "Screen protection active", "FaceLock responded to a security event"),
        }.get(state)
        if copy:
            if state == "locking_countdown":
                countdown = max(1, int((extra or {}).get("countdown", 3)))
                copy = (copy[0], f"Locking in {countdown} s", copy[2])
            self._apply_state(copy[0], copy, extra)
            if self.floating:
                self._present_floating_activity(
                    4000 if state == "locking_countdown" else 8000 if state in ("locked", "stranger_warning") else 5500
                )

    def _on_status_changed(self, status: str, description: str):
        if status == "paused" and "camera" in description.lower():
            self._apply_state("camera_busy", ("camera_busy", "Camera unavailable", "Another app is using the camera"))
        elif status == "paused":
            self._apply_state("paused", self._default_copy("paused"))
        elif status == "camera_busy":
            self._apply_state("camera_busy", ("camera_busy", "Camera unavailable", "Another app is using the camera"))
        elif status == "intruder" and self._state not in ("stranger_warning", "locking_countdown"):
            self._apply_state("stranger_warning", ("stranger_warning", "Security alert", "Review the latest activity"))
        elif status == "protected" and self._state in ("paused", "camera_busy", "locked", "stranger_warning", "locking_countdown"):
            self._apply_state("active", self._default_copy("active"))

    def _on_config_updated(self):
        if not self.floating:
            self.setVisible(bool(self.config.notifications_enabled))
        elif not self.config.notifications_enabled or not self.config.protection_enabled:
            self._dismiss_timer.stop()
            self._event_active = False
        self._sync_floating_visibility()

    def _on_owner_window_visibility(self, visible: bool):
        self._main_window_visible = bool(visible)
        if visible and self.floating:
            self._event_active = False
            self._dismiss_timer.stop()
        self._sync_floating_visibility()

    def _sync_floating_visibility(self):
        if not self.floating:
            return
        should_show = (
            not self._main_window_visible
            and self._event_active
            and self._monitoring_active
            and self.config.protection_enabled
            and self.config.notifications_enabled
        )
        if should_show:
            self._show_floating_animated()
        else:
            self.hide()

    def _show_floating_animated(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        bounds = screen.availableGeometry()
        width, height = 480, self.height()
        final_rect = QRectF(0, 0, width, height).toRect()
        final_rect.moveCenter(bounds.center())
        final_rect.moveTop(bounds.top() + 14)
        start_rect = QRectF(0, 0, 50, 50).toRect()
        start_rect.moveCenter(final_rect.center())
        was_hidden = not self.isVisible()
        self._activity_geometry = final_rect
        if was_hidden:
            self.setGeometry(start_rect)
            self.show()
        self.raise_()
        self._geometry_animation.stop()
        self._geometry_animation.setDuration(360)
        self._geometry_animation.setEasingCurve(QEasingCurve.OutBack)
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(final_rect)
        self._geometry_animation.start()

    def _present_floating_activity(self, duration_ms):
        if not self.floating or self._main_window_visible:
            return
        self._event_active = True
        self._sync_floating_visibility()
        self._dismiss_timer.start(duration_ms)

    def _dismiss_floating_activity(self):
        if not self.floating:
            return
        self._event_active = False
        if self._main_window_visible or not self.isVisible():
            self._sync_floating_visibility()
            return
        center = self.geometry().center()
        small = QRectF(0, 0, 50, 50).toRect()
        small.moveCenter(center)
        self._geometry_animation.stop()
        self._geometry_animation.setDuration(260)
        self._geometry_animation.setEasingCurve(QEasingCurve.InBack)
        self._geometry_animation.setStartValue(self.geometry())
        self._geometry_animation.setEndValue(small)
        self._geometry_animation.finished.connect(self._finish_dismiss_animation)
        self._geometry_animation.start()

    def _finish_dismiss_animation(self):
        try:
            self._geometry_animation.finished.disconnect(self._finish_dismiss_animation)
        except (RuntimeError, TypeError):
            pass
        self.hide()

    def _tick_countdown(self):
        elapsed = time.time() - self._countdown_started
        remaining = max(0.0, self._countdown_total - elapsed)
        self._progress = remaining / max(1, self._countdown_total)
        self.title.setText(f"Locking in {max(1, int(remaining + 0.999))} s")
        self.update()
        if remaining <= 0:
            self._countdown_timer.stop()

    def _cancel_countdown(self):
        self._countdown_timer.stop()
        events.hud_cancel_countdown.emit()
        self._apply_state("active", ("active", "Lock cancelled", "Protection remains active"))

    def _toggle_expanded(self):
        self._expanded = not self._expanded
        self.setFixedHeight(96 if self._expanded else 62)
        self.details.setVisible(self._expanded)
        self.open_button.setVisible(self._expanded)
        self.expand_button.setText("⌃" if self._expanded else "⌄")
        self.expand_button.setAccessibleName(
            "Collapse live activity details" if self._expanded else "Expand live activity details"
        )

    def _open_activity(self):
        if self.on_open_activity:
            self.on_open_activity()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        card = QRectF(self.rect()).adjusted(1, 1, -1, -2)
        gradient = QLinearGradient(card.topLeft(), card.bottomLeft())
        gradient.setColorAt(0.0, QColor("#1B1D22"))
        gradient.setColorAt(1.0, QColor("#101216"))
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(card, 22, 22)
        if self._state == "locking_countdown" and self._progress > 0:
            bar = QRectF(card.left() + 18, card.bottom() - 4, (card.width() - 36) * self._progress, 2)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#FF6961"))
            painter.drawRoundedRect(bar, 1, 1)
        painter.end()
