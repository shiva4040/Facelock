"""
FaceLock Dashboard Screen
Matches macOS Sonoma design specification exactly:
- Header: "Dashboard" + "Your laptop is guarded while you are away from the keyboard."
- Hero Card: 88px animated StatusRing, "STATUS", state text 28px bold,
  "Owner recognized X s ago | next check in Y s", "Pause 15 min" pill + master MacToggle.
- Stat row (3 cards): Checks today, Strangers flagged (red when > 0), Last check (HH:MM:SS).
- Bottom row:
  - Live preview card (290px): toggle off by default, dark box with camera icon & privacy message.
  - Today timeline card: 28px circular icons per event, title, 11px detail, right-aligned time, "See all" link.
"""
import time
from datetime import datetime
from typing import List, Tuple
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QFrame, QStackedWidget,
    QSizePolicy
)

from core.config import AppConfig
from core.events import events
from ui.theme import ThemeTokens
from ui.strings import Strings
from ui.components.card import MacCard
from ui.components.pill_button import PillButton
from ui.components.toggle import MacToggle
from ui.components.status_ring import StatusRing
from ui.components.camera_view import CameraView


def render_timeline_icon(kind: str, size: int = 28) -> QWidget:
    """Renders 28px circular vector icon for Today timeline."""
    w = QWidget()
    w.setFixedSize(size, size)

    def paint_icon(event):
        p = QPainter(w)
        p.setRenderHint(QPainter.Antialiasing)

        if kind == "welcome":
            bg = QColor("#E4F4EA")
            fg = QColor("#1B7F45")
        elif kind == "away":
            bg = QColor("#E6E6EA")
            fg = QColor("#5C5C63")
        elif kind == "locked":
            bg = QColor("#FDE8EA")
            fg = QColor("#C4001A")
        else:  # started / info
            bg = QColor("#D5E5FA")
            fg = QColor("#0066D6")

        # Circle background
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawEllipse(0, 0, size, size)

        # Foreground icon
        p.setPen(QPen(fg, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        cx = size / 2.0
        cy = size / 2.0
        p.translate(cx, cy)

        if kind == "welcome":
            # Checkmark
            path = QPainterPath()
            path.moveTo(-4, 0)
            path.lineTo(-1, 3.5)
            path.lineTo(4.5, -3)
            p.drawPath(path)
        elif kind == "away":
            # User outline
            p.drawEllipse(QRectF(-3.5, -6.5, 7, 7))
            p.drawArc(QRectF(-6.5, -0.5, 13, 11), 30 * 16, 120 * 16)
        elif kind == "locked":
            # Small lock
            p.drawRoundedRect(QRectF(-4.5, -1, 9, 7.5), 1.5, 1.5)
            p.drawArc(QRectF(-3, -5.5, 6, 6), 0, 180 * 16)
        else:
            # Shield
            path = QPainterPath()
            path.moveTo(0, -6)
            path.lineTo(5, -3.5)
            path.lineTo(5, 1)
            path.cubicTo(5, 4.5, 0, 6.5, 0, 6.5)
            path.cubicTo(0, 6.5, -5, 4.5, -5, 1)
            path.lineTo(-5, -3.5)
            path.closeSubpath()
            p.drawPath(path)

        p.end()

    w.paintEvent = paint_icon
    return w


class TimelineRow(QWidget):
    """Single row in the Today timeline."""
    def __init__(self, kind: str, title: str, subtitle: str, timestamp: str, has_divider: bool = True, parent=None):
        super().__init__(parent)
        self.has_divider = has_divider
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        # 28px circular icon
        self.icon_widget = render_timeline_icon(kind, size=28)
        layout.addWidget(self.icon_widget)

        # Text column
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setAlignment(Qt.AlignVCenter)

        t_lbl = QLabel(title, self)
        self.title_label = t_lbl
        t_lbl.setMinimumWidth(0)
        t_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        t_lbl.setToolTip(title)
        t_lbl.setFont(ThemeTokens.get_font(size_pt=13, weight=600))
        t_lbl.setStyleSheet("color: #1D1D1F;")
        text_col.addWidget(t_lbl)

        s_lbl = QLabel(subtitle, self)
        s_lbl.setFont(ThemeTokens.get_font(size_pt=11))
        s_lbl.setStyleSheet("color: #5C5C63;")
        s_lbl.setWordWrap(False)
        s_lbl.setMinimumWidth(0)
        s_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        s_lbl.setToolTip(subtitle)
        self.subtitle_label = s_lbl
        text_col.addWidget(s_lbl)

        layout.addLayout(text_col, 1)

        # Timestamp right
        time_lbl = QLabel(timestamp, self)
        self.time_label = time_lbl
        time_lbl.setFont(ThemeTokens.get_font(size_pt=12, weight=500, tabular=True))
        time_lbl.setStyleSheet("color: #5C5C63;")
        layout.addWidget(time_lbl)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.has_divider:
            p = QPainter(self)
            p.setPen(QPen(QColor("#EDEDF0"), 1.0))
            y = self.height() - 1
            # Divider starts after icon (40px)
            p.drawLine(40, y, self.width(), y)
            p.end()


class DashboardPage(QWidget):
    see_all_clicked = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._today_checks = 1284
        self._strangers_count = 2
        self._last_check_str = "09:41:07"
        self._last_recognized_time = time.time() - 4.0
        self._status_code = "protected"
        self._pause_timer = QTimer(self)
        self._pause_timer.setSingleShot(True)
        self._pause_timer.timeout.connect(self._on_pause_expired)

        self._build_ui()

        # Connect events
        events.status_changed.connect(self.on_status_changed)
        events.check_result.connect(self.on_check_result)
        events.intruder_recorded.connect(self.on_intruder_recorded)
        events.preview_frame.connect(self.on_preview_frame)

        # 1-second UI tick to update "Owner recognized X s ago | next check in Y s"
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._update_tick_labels)
        self._tick_timer.start(1000)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(34, 28, 34, 28)
        main_layout.setSpacing(16)

        # 1. Page Header
        h_title = QLabel(Strings.DASHBOARD_TITLE, self)
        h_title.setFont(ThemeTokens.get_font(size_pt=22, weight=600))
        h_title.setStyleSheet("color: #1D1D1F;")
        main_layout.addWidget(h_title)

        h_sub = QLabel(Strings.DASHBOARD_SUBTITLE, self)
        h_sub.setFont(ThemeTokens.get_font(size_pt=13))
        h_sub.setStyleSheet("color: #5C5C63;")
        main_layout.addWidget(h_sub)

        # 2. Hero Card (16px radius, padding 20-24px)
        hero_card = MacCard(is_hero=True, is_dark=False, parent=self)
        hero_card.setFixedSize(712, 132)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(20)

        # Left: 88px Status Ring
        self.status_ring = StatusRing(size=88, status="protected", is_dark=False, parent=hero_card)
        hero_layout.addWidget(self.status_ring)

        # Middle: State text stack
        status_text_col = QVBoxLayout()
        status_text_col.setSpacing(2)
        status_text_col.setAlignment(Qt.AlignVCenter)

        self.status_overline = QLabel("STATUS", hero_card)
        self.status_overline.setFont(ThemeTokens.get_font(size_pt=11, weight=700))
        self.status_overline.setStyleSheet("color: #1B7F45; letter-spacing: 0.5px;")
        status_text_col.addWidget(self.status_overline)

        self.status_title = QLabel("Protected", hero_card)
        self.status_title.setFont(ThemeTokens.get_font(size_pt=28, weight=700))
        self.status_title.setStyleSheet("color: #1D1D1F;")
        status_text_col.addWidget(self.status_title)

        self.status_subtitle = QLabel("Owner recognized 4 s ago | next check in 3 s", hero_card)
        self.status_subtitle.setFont(ThemeTokens.get_font(size_pt=13))
        self.status_subtitle.setStyleSheet("color: #5C5C63;")
        self.status_subtitle.setWordWrap(True)
        self.status_subtitle.setMinimumWidth(0)
        self.status_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        status_text_col.addWidget(self.status_subtitle)

        hero_layout.addLayout(status_text_col, 1)

        # Right: Pause Menu Pill + Master Toggle
        right_controls = QHBoxLayout()
        right_controls.setSpacing(14)
        right_controls.setAlignment(Qt.AlignVCenter)

        self.pause_btn = PillButton("⏸  Pause 15 min", variant="secondary", is_dark=False, parent=hero_card)
        self.pause_btn.clicked.connect(self._show_pause_menu)
        right_controls.addWidget(self.pause_btn)

        self.master_toggle = MacToggle(checked=self.config.protection_enabled, active_color="#1B7F45", accessible_name="Master protection toggle", parent=hero_card)
        self.master_toggle.toggled.connect(self._on_master_toggle)
        right_controls.addWidget(self.master_toggle)

        hero_layout.addLayout(right_controls)
        main_layout.addWidget(hero_card)

        # 3. Stat Row (3 Cards side by side)
        stat_row = QHBoxLayout()
        stat_row.setSpacing(14)

        # Card 1: Checks today
        card_checks = MacCard(is_hero=False, is_dark=False, parent=self)
        card_checks.setFixedSize(228, 78)
        c1 = QVBoxLayout(card_checks)
        c1.setContentsMargins(16, 12, 16, 12)
        c1.setSpacing(2)
        lbl1 = QLabel("Checks today", card_checks)
        lbl1.setFont(ThemeTokens.get_font(size_pt=12, weight=500))
        lbl1.setStyleSheet("color: #5C5C63;")
        c1.addWidget(lbl1)
        self.val_checks = QLabel("1,284", card_checks)
        self.val_checks.setFont(ThemeTokens.get_font(size_pt=28, weight=700, tabular=True))
        self.val_checks.setStyleSheet("color: #1D1D1F;")
        c1.addWidget(self.val_checks)
        stat_row.addWidget(card_checks)

        # Card 2: Strangers flagged (RED when > 0)
        card_strangers = MacCard(is_hero=False, is_dark=False, parent=self)
        card_strangers.setFixedSize(228, 78)
        c2 = QVBoxLayout(card_strangers)
        c2.setContentsMargins(16, 12, 16, 12)
        c2.setSpacing(2)
        lbl2 = QLabel("Strangers flagged", card_strangers)
        lbl2.setFont(ThemeTokens.get_font(size_pt=12, weight=500))
        lbl2.setStyleSheet("color: #5C5C63;")
        c2.addWidget(lbl2)
        self.val_strangers = QLabel("2", card_strangers)
        self.val_strangers.setFont(ThemeTokens.get_font(size_pt=28, weight=700, tabular=True))
        self.val_strangers.setStyleSheet("color: #C4001A;")  # Red when > 0
        c2.addWidget(self.val_strangers)
        stat_row.addWidget(card_strangers)

        # Card 3: Last check
        card_last = MacCard(is_hero=False, is_dark=False, parent=self)
        card_last.setFixedSize(228, 78)
        c3 = QVBoxLayout(card_last)
        c3.setContentsMargins(16, 12, 16, 12)
        c3.setSpacing(2)
        lbl3 = QLabel("Last check", card_last)
        lbl3.setFont(ThemeTokens.get_font(size_pt=12, weight=500))
        lbl3.setStyleSheet("color: #5C5C63;")
        c3.addWidget(lbl3)
        self.val_last = QLabel("09:41:07", card_last)
        self.val_last.setFont(ThemeTokens.get_font(size_pt=28, weight=700, tabular=True))
        self.val_last.setStyleSheet("color: #1D1D1F;")
        c3.addWidget(self.val_last)
        stat_row.addWidget(card_last)

        main_layout.addLayout(stat_row)

        # 4. Bottom Row (Live Preview Card 288px + Today Timeline Card 410px)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        # 4a. Left: Live preview card (288px)
        self.preview_card = MacCard(is_hero=False, is_dark=False, parent=self)
        self.preview_card.setFixedSize(288, 270)
        p_layout = QVBoxLayout(self.preview_card)
        p_layout.setContentsMargins(16, 14, 16, 14)
        p_layout.setSpacing(10)

        p_header = QHBoxLayout()
        p_title = QLabel("Live preview", self.preview_card)
        p_title.setFont(ThemeTokens.get_font(size_pt=13, weight=600))
        p_title.setStyleSheet("color: #1D1D1F;")
        p_header.addWidget(p_title)
        p_header.addStretch()

        self.preview_toggle = MacToggle(checked=self.config.live_preview, active_color="#1B7F45", accessible_name="Live preview toggle", parent=self.preview_card)
        self.preview_toggle.toggled.connect(self._on_preview_toggled)
        p_header.addWidget(self.preview_toggle)
        p_layout.addLayout(p_header)

        # Stack between Privacy Box and Camera View
        self.preview_stack = QStackedWidget(self.preview_card)
        self.preview_stack.setFixedHeight(205)

        # Privacy Box (Dark box with camera icon & privacy message)
        privacy_box = QFrame(self.preview_stack)
        privacy_box.setStyleSheet("""
            QFrame {
                background-color: #2C2C30;
                border-radius: 10px;
            }
        """)
        priv_layout = QVBoxLayout(privacy_box)
        priv_layout.setContentsMargins(20, 20, 20, 20)
        priv_layout.setSpacing(8)
        priv_layout.setAlignment(Qt.AlignCenter)

        # Camera Icon
        cam_icon = QLabel(privacy_box)
        cam_icon.setFixedSize(32, 26)
        def draw_cam(e):
            p = QPainter(cam_icon)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor("#8E8E93"), 1.8))
            p.drawRoundedRect(QRectF(2, 4, 28, 20), 4, 4)
            p.drawEllipse(QRectF(11, 9, 10, 10))
            p.end()
        cam_icon.paintEvent = draw_cam
        priv_layout.addWidget(cam_icon, 0, Qt.AlignCenter)

        priv_t = QLabel("Preview is off", privacy_box)
        priv_t.setFont(ThemeTokens.get_font(size_pt=13, weight=700))
        priv_t.setStyleSheet("color: #FFFFFF;")
        priv_t.setAlignment(Qt.AlignCenter)
        priv_layout.addWidget(priv_t)

        priv_d = QLabel("Off by default for privacy. The camera only opens for a moment at each check.", privacy_box)
        priv_d.setFont(ThemeTokens.get_font(size_pt=11))
        priv_d.setStyleSheet("color: #8E8E93; line-height: 14px;")
        priv_d.setAlignment(Qt.AlignCenter)
        priv_d.setWordWrap(True)
        priv_layout.addWidget(priv_d)

        self.preview_stack.addWidget(privacy_box)

        # Real Live Camera View
        self.camera_view = CameraView(circular_mask=False, parent=self.preview_stack)
        self.preview_stack.addWidget(self.camera_view)

        self.preview_stack.setCurrentIndex(1 if self.config.live_preview else 0)
        p_layout.addWidget(self.preview_stack)

        bottom_row.addWidget(self.preview_card)

        # 4b. Right: Today Timeline Card (410px)
        today_card = MacCard(is_hero=False, is_dark=False, parent=self)
        today_card.setFixedSize(410, 270)
        t_layout = QVBoxLayout(today_card)
        t_layout.setContentsMargins(18, 14, 18, 14)
        t_layout.setSpacing(4)

        t_header = QHBoxLayout()
        t_title = QLabel("Today", today_card)
        t_title.setFont(ThemeTokens.get_font(size_pt=14, weight=600))
        t_title.setStyleSheet("color: #1D1D1F;")
        t_header.addWidget(t_title)
        t_header.addStretch()

        see_all_btn = QPushButton("See all", today_card)
        see_all_btn.setCursor(Qt.PointingHandCursor)
        see_all_btn.setFont(ThemeTokens.get_font(size_pt=13, weight=500))
        see_all_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0066D6;
                border: none;
                padding: 0;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        see_all_btn.clicked.connect(self.see_all_clicked)
        t_header.addWidget(see_all_btn)
        t_layout.addLayout(t_header)
        t_layout.addSpacing(6)

        # 4 Timeline Event Rows matching uploaded design exactly
        row1 = TimelineRow("welcome", "Welcome back", "Owner recognized", "09:41", has_divider=True, parent=today_card)
        row2 = TimelineRow("away", "Owner away", "Nobody in frame, still monitoring", "09:26", has_divider=True, parent=today_card)
        row3 = TimelineRow("locked", "Locked: unknown person", "Two checks in a row, photo saved", "09:03", has_divider=True, parent=today_card)
        row4 = TimelineRow("started", "Protection started", "Balanced preset", "08:58", has_divider=False, parent=today_card)

        t_layout.addWidget(row1)
        t_layout.addWidget(row2)
        t_layout.addWidget(row3)
        t_layout.addWidget(row4)

        bottom_row.addWidget(today_card)
        main_layout.addLayout(bottom_row)

    def _show_pause_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E8;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
                color: #1D1D1F;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #0066D6;
                color: #FFFFFF;
            }
        """)
        a15 = menu.addAction("Pause for 15 minutes")
        a60 = menu.addAction("Pause for 1 hour")
        atom = menu.addAction("Pause until tomorrow")

        action = menu.exec(self.pause_btn.mapToGlobal(self.pause_btn.rect().bottomLeft()))
        if action == a15:
            self._pause_for(15 * 60)
        elif action == a60:
            self._pause_for(60 * 60)
        elif action == atom:
            self._pause_for(24 * 60 * 60)

    def _pause_for(self, seconds: int):
        self.config.update(protection_enabled=False)
        self.master_toggle.setCheckedQuietly(False)
        self.on_status_changed("paused", "Monitoring Paused")
        self.pause_btn.setText(f"Paused ({seconds // 60}m)")
        self._pause_timer.start(seconds * 1000)

    def _on_pause_expired(self):
        self.config.update(protection_enabled=True)
        self.master_toggle.setCheckedQuietly(True)
        self.on_status_changed("protected", "Guarding Active")
        self.pause_btn.setText("⏸  Pause 15 min")

    def _on_master_toggle(self, enabled: bool):
        self.config.update(protection_enabled=enabled)
        if enabled:
            self._pause_timer.stop()
            self.pause_btn.setText("⏸  Pause 15 min")
            events.status_changed.emit("protected", "Guarding Active")
        else:
            events.status_changed.emit("paused", "Monitoring Paused")

    def _on_preview_toggled(self, enabled: bool):
        self.config.update(live_preview=enabled)
        self.preview_stack.setCurrentIndex(1 if enabled else 0)

    def _update_tick_labels(self):
        if self._status_code == "protected":
            ago = int(max(0, time.time() - self._last_recognized_time))
            next_in = max(1, int(self.config.check_interval_sec - (ago % self.config.check_interval_sec)))
            self.status_subtitle.setText(f"Owner recognized {ago} s ago | next check in {next_in} s")

    def on_status_changed(self, status: str, description: str):
        self._status_code = status
        self.status_ring.setStatus(status)

        if status == "protected":
            self.status_overline.setText("STATUS")
            self.status_overline.setStyleSheet("color: #1B7F45; letter-spacing: 0.5px; background-color: transparent;")
            self.status_title.setText("Protected")
            self.master_toggle.setCheckedQuietly(True)
        elif status == "paused":
            self.status_overline.setText("STATUS")
            self.status_overline.setStyleSheet("color: #8E8E93; letter-spacing: 0.5px; background-color: transparent;")
            self.status_title.setText("Paused")
            self.status_subtitle.setText("Monitoring is paused")
            self.master_toggle.setCheckedQuietly(False)
        elif status == "intruder":
            self.status_overline.setText("SECURITY ALERT")
            self.status_overline.setStyleSheet("color: #C4001A; letter-spacing: 0.5px; background-color: transparent;")
            self.status_title.setText("Intruder detected")
            self.status_subtitle.setText("Locking countdown initiated")
        elif status == "camera_busy":
            self.status_overline.setText("STANDBY")
            self.status_overline.setStyleSheet("color: #8A5300; letter-spacing: 0.5px; background-color: transparent;")
            self.status_title.setText("Camera busy")
            self.status_subtitle.setText("Video call in progress elsewhere")

    def on_check_result(self, meta: dict):
        self._today_checks += 1
        self.val_checks.setText(f"{self._today_checks:,}")
        self._last_check_str = time.strftime("%H:%M:%S", time.localtime(meta.get("timestamp", time.time())))
        self.val_last.setText(self._last_check_str)

        if meta.get("owner_present", False):
            self._last_recognized_time = time.time()

        if meta.get("stranger_present", False):
            self._strangers_count += 1
            self.val_strangers.setText(str(self._strangers_count))
            self.val_strangers.setStyleSheet("color: #C4001A; background-color: transparent;")

    def on_intruder_recorded(self, snapshot_path: str, score: float, timestamp_str: str):
        self._strangers_count += 1
        self.val_strangers.setText(str(self._strangers_count))
        self.val_strangers.setStyleSheet("color: #C4001A; background-color: transparent;")

    def on_preview_frame(self, frame, faces):
        if self.config.live_preview:
            self.camera_view.update_frame(frame, faces)
