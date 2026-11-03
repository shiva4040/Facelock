"""
FaceLock Privacy Overlay Lock Screen
A modern macOS-styled fullscreen privacy screen that secures the laptop in user-space
and automatically dismisses the moment the owner's face is recognized, with a PIN fallback.
"""
import time
import logging
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QApplication, QMessageBox
)

from core.config import AppConfig
from core.events import events
from ui.components.pill_button import PillButton

logger = logging.getLogger("facelock.overlay")


class PinDialog(QWidget):
    """Clean macOS style numeric PIN entry container."""
    def __init__(self, config: AppConfig, on_success_cb, parent=None):
        super().__init__(parent)
        self.config = config
        self.on_success_cb = on_success_cb
        self.setFixedSize(300, 160)
        self.setStyleSheet("""
            PinDialog {
                background-color: #242429;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Enter Master PIN", self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        self.pin_input = QLineEdit(self)
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setMaxLength(8)
        self.pin_input.setPlaceholderText("••••")
        self.pin_input.setStyleSheet("""
            QLineEdit {
                background-color: #18181C;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 8px;
                font-size: 20px;
                color: #FFFFFF;
                letter-spacing: 6px;
            }
            QLineEdit:focus {
                border: 1px solid #0A84FF;
            }
        """)
        self.pin_input.returnPressed.connect(self._verify)
        layout.addWidget(self.pin_input)

        btn_row = QHBoxLayout()
        cancel_btn = PillButton("Cancel", variant="secondary", parent=self)
        cancel_btn.clicked.connect(self.hide)
        btn_row.addWidget(cancel_btn)

        unlock_btn = PillButton("Unlock", variant="primary", parent=self)
        unlock_btn.clicked.connect(self._verify)
        btn_row.addWidget(unlock_btn)

        layout.addLayout(btn_row)

    def show_dialog(self):
        self.pin_input.clear()
        self.show()
        self.pin_input.setFocus()

    def _verify(self):
        entered = self.pin_input.text().strip()
        # A configured Master PIN is required; never accept a built-in fallback.
        if self.config.overlay_pin_hash and self.config.verify_pin(entered):
            self.hide()
            self.on_success_cb()
        else:
            self.pin_input.clear()
            self.pin_input.setPlaceholderText(
                "Incorrect PIN" if self.config.overlay_pin_hash else "Set Master PIN in Settings"
            )
            self.pin_input.setStyleSheet("""
                QLineEdit {
                    background-color: #18181C;
                    border: 1px solid #FF453A;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 18px;
                    color: #FF453A;
                }
            """)


class OverlayLockScreen(QWidget):
    """
    macOS Ventura / Sonoma styled fullscreen privacy lock screen.
    Automatically unlocks when owner's face is recognized.
    """

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._is_active = False

        self._init_window_flags()
        self._build_ui()
        self._setup_clock()

        # Connect events
        events.overlay_lock_requested.connect(self.lock)
        events.status_changed.connect(self._on_status_changed)

    def _init_window_flags(self):
        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Window
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

    def _build_ui(self):
        self.setStyleSheet("background-color: #0E0E12;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setAlignment(Qt.AlignCenter)

        # 1. Top Clock & Date Stack
        self.time_label = QLabel("10:00", self)
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.95);
            font-family: -apple-system, "SF Pro Display", "Segoe UI", sans-serif;
            font-size: 72px;
            font-weight: 300;
        """)
        layout.addWidget(self.time_label)

        self.date_label = QLabel("Monday, November 3", self)
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.65);
            font-family: -apple-system, "SF Pro Text", "Segoe UI", sans-serif;
            font-size: 18px;
            font-weight: 500;
        """)
        layout.addWidget(self.date_label)

        layout.addSpacing(40)

        # 2. Central Lock / Biometric Card
        self.card = QWidget(self)
        self.card.setFixedSize(380, 240)
        self.card.setStyleSheet("""
            QWidget {
                background-color: rgba(36, 36, 42, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 18px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(12)

        # Scanning Icon
        self.icon_label = QLabel(self.card)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self._update_icon(scanning=True)
        card_layout.addWidget(self.icon_label)

        # Status prompt
        self.status_title = QLabel("Laptop Locked", self.card)
        self.status_title.setAlignment(Qt.AlignCenter)
        self.status_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: 600; border: none; background: transparent;")
        card_layout.addWidget(self.status_title)

        self.status_sub = QLabel("Scanning for owner to resume...", self.card)
        self.status_sub.setAlignment(Qt.AlignCenter)
        self.status_sub.setStyleSheet("color: #8E8E93; font-size: 13px; border: none; background: transparent;")
        card_layout.addWidget(self.status_sub)

        # PIN Fallback button
        self.pin_btn = PillButton("Enter PIN", variant="secondary", parent=self.card)
        self.pin_btn.setFixedWidth(110)
        self.pin_btn.clicked.connect(self._show_pin_dialog)
        card_layout.addWidget(self.pin_btn, 0, Qt.AlignCenter)

        layout.addWidget(self.card, 0, Qt.AlignCenter)
        layout.addStretch()

        # Embedded PIN dialog (hidden by default)
        self.pin_dialog = PinDialog(self.config, on_success_cb=self.unlock, parent=self)
        self.pin_dialog.hide()

    def _setup_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._update_clock()
        self._clock_timer.start()

    def _update_clock(self):
        now = datetime.now()
        self.time_label.setText(now.strftime("%I:%M"))
        self.date_label.setText(now.strftime("%A, %B %d"))

    def _update_icon(self, scanning: bool = True, matched: bool = False):
        size = 54
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)

        color = QColor(52, 199, 89) if matched else (QColor(10, 132, 255) if scanning else QColor(255, 69, 58))
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(4, 4, 46, 46)

        # Lock body
        p.setBrush(QColor(255, 255, 255))
        p.drawRoundedRect(17, 24, 20, 15, 3, 3)

        # Shackle
        p.setPen(QPen(QColor(255, 255, 255), 2.5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(21, 14, 12, 14, 0, 180 * 16)
        p.end()

        self.icon_label.setPixmap(pm)

    def _show_pin_dialog(self):
        # Center pin dialog over card
        x = (self.width() - self.pin_dialog.width()) // 2
        y = (self.height() - self.pin_dialog.height()) // 2
        self.pin_dialog.move(x, y)
        self.pin_dialog.show_dialog()

    def lock(self):
        """Shows the fullscreen lock overlay."""
        self._is_active = True
        self._update_icon(scanning=True, matched=False)
        self.status_title.setText("Laptop Locked")
        self.status_sub.setText("Scanning for owner to resume...")

        # Cover entire screen geometry
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        logger.info("Overlay lock screen displayed.")

    def unlock(self):
        """Unlocks and hides the privacy overlay."""
        if not self._is_active:
            return

        self._is_active = False
        self._update_icon(scanning=False, matched=True)
        self.status_title.setText("Owner Verified")
        self.status_sub.setText("Welcome back!")

        QTimer.singleShot(400, self._finish_unlock)

    def _finish_unlock(self):
        self.hide()
        events.overlay_unlocked.emit()
        logger.info("Overlay lock screen dismissed.")

    def _on_status_changed(self, status: str, description: str):
        """If owner appears while locked, auto-dismiss!"""
        if self._is_active and status == "protected" and "Owner Present" in description:
            self.unlock()

    def keyPressEvent(self, event):
        # Allow typing ESC or P to open PIN dialog
        if event.key() == Qt.Key_Escape:
            self._show_pin_dialog()
        super().keyPressEvent(event)

