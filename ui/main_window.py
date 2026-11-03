"""
FaceLock Main Window Shell
macOS Ventura / Sonoma styled frameless native desktop interface.
Shell dimensions: default 1000x640, minimum 900x600.
Coordinates Sidebar navigation (220px), QStackedWidget content area,
window dragging, system tray minimization, and Windows 11 Mica/Acrylic effects.
"""
import sys
import platform
import logging
from PySide6.QtCore import Qt, QPoint, QRect, QSize, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QApplication, QScrollArea
)

from core.config import AppConfig
from core.events import events
from ui.sidebar import Sidebar
from ui.theme import ThemeTokens, clear_label_backplates
from ui.live_activity import LiveActivityBar
from ui.window_effects import apply_mica_or_acrylic
from ui.pages.dashboard_page import DashboardPage
from ui.pages.owner_face_page import OwnerFacePage
from ui.pages.security_page import SecurityPage
from ui.pages.intruder_log_page import IntruderLogPage
from ui.pages.settings_page import SettingsPage

logger = logging.getLogger("facelock.window")
IS_WINDOWS = platform.system() == "Windows"


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._drag_pos = QPoint()
        self._is_maximized_custom = False
        self._normal_geom = None
        self.setWindowTitle("FaceLock")

        self._init_window_flags()
        self._apply_theme()
        self._build_ui()

        # Connect theme changes
        events.config_updated.connect(self._apply_theme)

    def _init_window_flags(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        # DWM Mica and a translucent Qt top-level window leave stale/black
        # backing pixels around native text on some Windows GPU drivers.
        # Keep the app surface opaque; rounded corners are supplied by DWM.
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1000, 640)
        self.setMinimumSize(900, 600)

    def _apply_theme(self):
        mode = self.config.theme
        if mode == "system":
            # The supplied macOS-style references use the light palette. Keep
            # legacy "system" configs on that palette; dark is an explicit choice.
            mode = "light"
        self.tokens = ThemeTokens(mode)
        self.setStyleSheet(self.tokens.get_stylesheet())

        if hasattr(self, "root") and self.root:
            self.root.setStyleSheet(
                f"QWidget#CentralRoot {{ background-color: {self.tokens.window_bg}; border-radius: 12px; }}"
            )

        if hasattr(self, "sidebar") and self.sidebar:
            self.sidebar.setDarkTheme(self.tokens.is_dark)
        if hasattr(self, "content_stack") and self.content_stack:
            self.content_stack.setStyleSheet(f"background-color: {self.tokens.window_bg};")

    def _build_ui(self):
        # Central root container with rounded borders
        self.root = QWidget(self)
        self.root.setObjectName("CentralRoot")
        self.root.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(self.root)

        root_layout = QHBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Sidebar on Left (fixed 220px)
        self.sidebar = Sidebar(is_dark=self.tokens.is_dark, parent=self.root)
        self.sidebar.page_changed.connect(self._on_page_changed)
        self.sidebar.close_clicked.connect(self._handle_close)
        self.sidebar.minimize_clicked.connect(self.showMinimized)
        self.sidebar.maximize_clicked.connect(self._toggle_maximize)
        root_layout.addWidget(self.sidebar)

        # 2. Content Stack on Right (780px)
        self.content_stack = QStackedWidget(self.root)
        self.content_stack.setStyleSheet(f"background-color: {self.tokens.window_bg};")

        self.dashboard_page = DashboardPage(self.config, self.content_stack)
        self.dashboard_page.see_all_clicked.connect(lambda: self.sidebar.select_page(3))
        self.owner_face_page = OwnerFacePage(self.config, self.content_stack)
        self.security_page = SecurityPage(self.config, self.content_stack)
        self.intruder_log_page = IntruderLogPage(self.config, self.content_stack)
        self.settings_page = SettingsPage(self.config, self.content_stack)

        self.content_stack.addWidget(self.dashboard_page)
        self.content_stack.addWidget(self.owner_face_page)
        self.content_stack.addWidget(self.security_page)
        self.content_stack.addWidget(self.intruder_log_page)
        self.content_stack.addWidget(self.settings_page)

        # Persistent hidden live_activity for backward compatibility
        self.live_activity = LiveActivityBar(
            self.config,
            on_open_activity=lambda: self.sidebar.select_page(3),
            parent=self.root,
        )
        self.live_activity.hide()

        clear_label_backplates(self.root)

        root_layout.addWidget(self.content_stack, 1)

    def showEvent(self, event):
        super().showEvent(event)
        events.window_visibility_changed.emit(not self.isMinimized())
        # Apply Windows 11 Mica / Acrylic effects to window handle
        try:
            hwnd = int(self.winId())
            dark = self.tokens.is_dark
            apply_mica_or_acrylic(hwnd, dark=dark)
        except Exception:
            pass

    def hideEvent(self, event):
        super().hideEvent(event)
        events.window_visibility_changed.emit(False)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            events.window_visibility_changed.emit(self.isVisible() and not self.isMinimized())

    def _on_page_changed(self, index: int):
        self.content_stack.setCurrentIndex(index)
        # Auto refresh activity/intruder log when navigated to
        if index == 3 and hasattr(self.intruder_log_page, "refresh_gallery"):
            self.intruder_log_page.refresh_gallery()

    def _handle_close(self):
        # macOS style: closing window minimizes to system tray
        self.hide()

    def _toggle_maximize(self):
        if self._is_maximized_custom:
            if self._normal_geom:
                self.setGeometry(self._normal_geom)
            self._is_maximized_custom = False
        else:
            self._normal_geom = self.geometry()
            screen = self.screen() or QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
            self._is_maximized_custom = True

    # Window Dragging implementation
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Allow dragging if clicked in top header area (first 50px)
            if event.position().y() <= 50:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            if not self._is_maximized_custom:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent):
        # Minimize to tray instead of quitting
        event.ignore()
        self.hide()

    def paintEvent(self, event):
        # Draw 12px rounded rectangle with 1px hairline border
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        bg = QColor(self.tokens.window_bg)
        border = QColor(self.tokens.sidebar_border)

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(rect, 12, 12)
        painter.end()
