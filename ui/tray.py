"""
FaceLock System Tray
macOS-styled system tray integration with status indicator, dynamic icon rendering,
and control menu (Pause/Resume, Open Window, Quit).
"""
import logging
from typing import Callable, Optional
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QAction, QFont
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from core.events import events
from core.config import AppConfig

logger = logging.getLogger("facelock.tray")


def create_tray_pixmap(status: str = "protected", size: int = 32) -> QPixmap:
    """
    Renders a crisp vector-style shield & lock icon with status indicator dot.
    Status can be 'protected' (green), 'paused' (amber/gray), 'intruder' (red).
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Base shield outline
    scale = size / 32.0
    pen_color = QColor(255, 255, 255) if status == "protected" else QColor(200, 200, 200)
    painter.setPen(QPen(pen_color, 2.0 * scale))
    painter.setBrush(QBrush(QColor(30, 30, 35, 220)))

    # Draw rounded shield / lock body
    body_x = int(6 * scale)
    body_y = int(10 * scale)
    body_w = int(20 * scale)
    body_h = int(18 * scale)
    painter.drawRoundedRect(body_x, body_y, body_w, body_h, 4 * scale, 4 * scale)

    # Shackle arch
    shackle_pen = QPen(pen_color, 2.2 * scale)
    painter.setPen(shackle_pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(int(10 * scale), int(4 * scale), int(12 * scale), int(14 * scale), 0, 180 * 16)

    # Status color dot in bottom right
    status_colors = {
        "protected": QColor(52, 199, 89),    # macOS Green
        "paused": QColor(255, 159, 10),      # macOS Amber
        "intruder": QColor(255, 69, 58),     # macOS Red
        "absent": QColor(142, 142, 147),    # macOS Gray
    }
    dot_color = status_colors.get(status, QColor(52, 199, 89))

    dot_r = int(4.5 * scale)
    dot_cx = int(size - dot_r - 2)
    dot_cy = int(size - dot_r - 2)

    painter.setPen(QPen(QColor(15, 15, 18), 1.5 * scale))
    painter.setBrush(QBrush(dot_color))
    painter.drawEllipse(dot_cx - dot_r, dot_cy - dot_r, dot_r * 2, dot_r * 2)

    painter.end()
    return pixmap


class FaceLockTray(QSystemTrayIcon):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._current_status = "protected" if config.protection_enabled else "paused"
        self._toggle_window_cb: Optional[Callable[[], None]] = None
        self._toggle_protect_cb: Optional[Callable[[], None]] = None
        self._simulate_lock_cb: Optional[Callable[[], None]] = None
        self._lock_now_cb: Optional[Callable[[], None]] = None

        self.setIcon(QIcon(create_tray_pixmap(self._current_status)))
        self.setToolTip("FaceLock: Protected" if config.protection_enabled else "FaceLock: Paused")

        self._build_menu()
        self.activated.connect(self._on_tray_activated)

        # Connect event bus signals
        events.status_changed.connect(self.on_status_changed)

    def set_callbacks(self, toggle_window, toggle_protect, simulate_lock=None, lock_now=None):
        self._toggle_window_cb = toggle_window
        self._toggle_protect_cb = toggle_protect
        self._simulate_lock_cb = simulate_lock
        self._lock_now_cb = lock_now

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E24;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px;
                color: #FFFFFF;
                font-family: -apple-system, "SF Pro Text", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 5px;
            }
            QMenu::item:selected {
                background-color: #0A84FF;
                color: #FFFFFF;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.12);
                margin: 4px 6px;
            }
        """)

        self.status_action = QAction("FaceLock: Active", menu)
        self.status_action.setEnabled(False)
        menu.addAction(self.status_action)

        menu.addSeparator()

        self.toggle_action = QAction("Pause Protection", menu)
        self.toggle_action.triggered.connect(self._handle_toggle_protect)
        menu.addAction(self.toggle_action)

        self.open_action = QAction("Open FaceLock", menu)
        self.open_action.triggered.connect(self._handle_open_window)
        menu.addAction(self.open_action)

        if self._simulate_lock_cb:
            self.test_action = QAction("Test Lock (Simulate)", menu)
            self.test_action.triggered.connect(self._simulate_lock_cb)
            menu.addAction(self.test_action)

        self.lock_now_action = QAction("Lock Screen Now", menu)
        self.lock_now_action.triggered.connect(self._handle_lock_now)
        menu.addAction(self.lock_now_action)

        menu.addSeparator()

        self.quit_action = QAction("Quit FaceLock", menu)
        self.quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(self.quit_action)

        self.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._handle_open_window()

    def _handle_open_window(self):
        if self._toggle_window_cb:
            self._toggle_window_cb()

    def _handle_lock_now(self):
        if self._lock_now_cb:
            self._lock_now_cb()

    def _handle_toggle_protect(self):
        if self._toggle_protect_cb:
            self._toggle_protect_cb()

    def on_status_changed(self, status: str, description: str):
        self._current_status = status
        self.setIcon(QIcon(create_tray_pixmap(status)))
        self.setToolTip(f"FaceLock: {description}")

        if status == "paused":
            self.status_action.setText("FaceLock: Paused")
            self.toggle_action.setText("Resume Protection")
        else:
            self.status_action.setText(f"FaceLock: {description}")
            self.toggle_action.setText("Pause Protection")

