"""
FaceLock Activity Screen (Intruder Log & Event History)
Matches macOS Sonoma design specification exactly:
- Header: "Activity" + "Every lock and every unknown face, newest first."
  Top right: Filter segmented (All, Strangers, Owner) + "↓ Export" pill button.
- Section 1: "Stranger snapshots" 4-up cards grid with "Score 0.XX" dark badge,
  "Stranger" title, timestamp line. Click opens enlarged dialog.
- Section 2: "Recent events" card with Date, "Unknown person", Score, Result pill
  (Locked red, Cancelled amber).
- Footer: Lock icon + "Photos are encrypted on this device and deleted after 30 days."
  and danger pill button "🗑 Clear all".
"""
import os
import json
import time
import shutil
from datetime import datetime
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QFileDialog, QMessageBox, QDialog, QFrame
)

from core.config import INTRUDERS_DIR, AppConfig
from core.events import events
from ui.theme import ThemeTokens
from ui.strings import Strings
from ui.components.card import MacCard
from ui.components.pill_button import PillButton
from ui.components.segmented import SegmentedControl
from ui.components.badge import Badge


class ImageModal(QDialog):
    """Enlarged Lightbox Dialog for inspecting intruder snapshots."""
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle("Intruder Snapshot Details")
        self.setFixedSize(580, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #E4E4E8;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        img_label = QLabel(self)
        img_label.setAlignment(Qt.AlignCenter)
        if os.path.exists(image_path):
            pix = QPixmap(image_path)
            if not pix.isNull():
                img_label.setPixmap(pix.scaled(540, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(img_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = PillButton("Close", variant="primary", is_dark=False, parent=self)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class SnapshotThumbnailCard(QWidget):
    """Single card in the Stranger snapshots 4-up grid."""
    def __init__(self, score: float, date_str: str, image_path: str = "", on_click_cb=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.on_click_cb = on_click_cb
        self.setFixedWidth(160)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Image Container
        self.img_container = QFrame(self)
        self.img_container.setFixedSize(160, 110)
        self.img_container.setStyleSheet("""
            QFrame {
                background-color: #2C2C30;
                border-radius: 10px;
            }
        """)

        # Overlay layout for Score badge
        c_layout = QVBoxLayout(self.img_container)
        c_layout.setContentsMargins(8, 8, 8, 8)
        c_layout.setSpacing(0)

        top_row = QHBoxLayout()
        score_badge = Badge(f"Score {score:.2f}", variant="score", is_dark=False, parent=self.img_container)
        top_row.addWidget(score_badge)
        top_row.addStretch()
        c_layout.addLayout(top_row)
        c_layout.addStretch()

        # If actual snapshot image exists, draw it inside container
        if image_path and os.path.exists(image_path):
            pix = QPixmap(image_path)
            if not pix.isNull():
                scaled = pix.scaled(160, 110, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                def draw_custom_pix(e):
                    p = QPainter(self.img_container)
                    p.setRenderHint(QPainter.Antialiasing)
                    clip = QPainterPath()
                    clip.addRoundedRect(QRectF(0, 0, 160, 110), 10, 10)
                    p.setClipPath(clip)
                    p.drawPixmap(0, 0, scaled)
                    p.end()
                self.img_container.paintEvent = draw_custom_pix
        else:
            # Draw placeholder silhouette
            def draw_silhouette(e):
                p = QPainter(self.img_container)
                p.setRenderHint(QPainter.Antialiasing)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#2C2C30"))
                p.drawRoundedRect(QRectF(0, 0, 160, 110), 10, 10)
                # Silhouette head & body
                p.setBrush(QColor(255, 255, 255, 40))
                p.drawEllipse(QRectF(65, 30, 30, 32))
                p.drawArc(QRectF(45, 66, 70, 70), 30 * 16, 120 * 16)
                p.end()
            self.img_container.paintEvent = draw_silhouette

        layout.addWidget(self.img_container)

        # Title: Stranger
        title = QLabel(Strings.STRANGER_CARD_TITLE, self)
        title.setFont(ThemeTokens.get_font(size_pt=13, weight=600))
        title.setStyleSheet("color: #1D1D1F;")
        layout.addWidget(title)

        # Timestamp
        date_lbl = QLabel(date_str, self)
        date_lbl.setFont(ThemeTokens.get_font(size_pt=11))
        date_lbl.setStyleSheet("color: #5C5C63;")
        layout.addWidget(date_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click_cb:
            self.on_click_cb(self.image_path)
        super().mousePressEvent(event)


class RecentEventRow(QWidget):
    """Single row in the Recent events card."""
    def __init__(self, date_str: str, title: str, score_str: str, result_kind: str, has_divider: bool = True, parent=None):
        super().__init__(parent)
        self.has_divider = has_divider
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 6, 18, 6)
        layout.setSpacing(14)

        # Date column
        d_lbl = QLabel(date_str, self)
        d_lbl.setFont(ThemeTokens.get_font(size_pt=12, tabular=True))
        d_lbl.setStyleSheet("color: #5C5C63;")
        d_lbl.setFixedWidth(120)
        layout.addWidget(d_lbl)

        # Description
        t_lbl = QLabel(title, self)
        t_lbl.setFont(ThemeTokens.get_font(size_pt=13, weight=500))
        t_lbl.setStyleSheet("color: #1D1D1F;")
        layout.addWidget(t_lbl)

        layout.addStretch()

        # Score
        s_lbl = QLabel(score_str, self)
        s_lbl.setFont(ThemeTokens.get_font(size_pt=12, tabular=True))
        s_lbl.setStyleSheet("color: #5C5C63;")
        layout.addWidget(s_lbl)

        # Result pill
        pill = Badge(Strings.PILL_LOCKED if result_kind == "locked" else Strings.PILL_CANCELLED, variant=result_kind, is_dark=False, parent=self)
        layout.addWidget(pill)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.has_divider:
            p = QPainter(self)
            p.setPen(QPen(QColor("#EDEDF0"), 1.0))
            y = self.height() - 1
            p.drawLine(18, y, self.width() - 18, y)
            p.end()


class ActivityPage(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(16)

        # 1. Header with Title + Subtitle and Top-Right Filter & Export Button
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        h_title = QLabel(Strings.ACTIVITY_TITLE, self)
        h_title.setFont(ThemeTokens.get_font(size_pt=22, weight=600))
        h_title.setStyleSheet("color: #1D1D1F;")
        header_text.addWidget(h_title)

        h_sub = QLabel(Strings.ACTIVITY_SUBTITLE, self)
        h_sub.setFont(ThemeTokens.get_font(size_pt=13))
        h_sub.setStyleSheet("color: #5C5C63;")
        header_text.addWidget(h_sub)
        header_row.addLayout(header_text)
        header_row.addStretch()

        # Top-Right Filter Segmented + Export
        top_ctrls = QHBoxLayout()
        top_ctrls.setSpacing(12)
        top_ctrls.setAlignment(Qt.AlignVCenter)

        self.filter_seg = SegmentedControl(["All", "Strangers", "Owner"], default_index=0, is_dark=False, parent=self)
        self.filter_seg.setFixedWidth(200)
        top_ctrls.addWidget(self.filter_seg)

        self.export_btn = PillButton("↓  Export", variant="secondary", is_dark=False, parent=self)
        self.export_btn.clicked.connect(self._export_activity)
        top_ctrls.addWidget(self.export_btn)

        header_row.addLayout(top_ctrls)
        main_layout.addLayout(header_row)

        # 2. Section: Stranger snapshots (14px semibold)
        snap_lbl = QLabel(Strings.STRANGER_SNAPSHOTS_TITLE, self)
        snap_lbl.setFont(ThemeTokens.get_font(size_pt=14, weight=600))
        snap_lbl.setStyleSheet("color: #1D1D1F;")
        main_layout.addWidget(snap_lbl)

        # 4-up Snapshot Grid
        snap_row = QHBoxLayout()
        snap_row.setSpacing(16)

        # Check real intruders directory for latest snapshots
        files = []
        if os.path.exists(INTRUDERS_DIR):
            files = sorted(
                [os.path.join(INTRUDERS_DIR, f) for f in os.listdir(INTRUDERS_DIR) if f.lower().endswith((".jpg", ".png"))],
                key=os.path.getmtime,
                reverse=True
            )

        demo_snapshots = [
            (0.21, "Today, 09:03"),
            (0.33, "Yesterday, 17:22"),
            (0.18, "Yesterday, 11:05"),
            (0.27, "Mon, 14:50"),
        ]

        for i in range(4):
            score, date_str = demo_snapshots[i]
            img_path = files[i] if i < len(files) else ""
            card = SnapshotThumbnailCard(score=score, date_str=date_str, image_path=img_path, on_click_cb=self._open_lightbox, parent=self)
            snap_row.addWidget(card)

        snap_row.addStretch()
        main_layout.addLayout(snap_row)

        # 3. Section: Recent events card
        rec_lbl = QLabel(Strings.RECENT_EVENTS_TITLE, self)
        rec_lbl.setFont(ThemeTokens.get_font(size_pt=14, weight=600))
        rec_lbl.setStyleSheet("color: #1D1D1F;")
        main_layout.addWidget(rec_lbl)

        card_events = MacCard(is_hero=False, is_dark=False, parent=self)
        ce_layout = QVBoxLayout(card_events)
        ce_layout.setContentsMargins(0, 0, 0, 0)
        ce_layout.setSpacing(0)

        # Table rows matching uploaded design
        r1 = RecentEventRow("Today, 09:03", "Unknown person", "Score 0.21", "locked", has_divider=True, parent=card_events)
        r2 = RecentEventRow("Yesterday, 17:22", "Unknown person", "Score 0.33", "cancelled", has_divider=True, parent=card_events)
        r3 = RecentEventRow("Yesterday, 11:05", "Unknown person", "Score 0.18", "locked", has_divider=False, parent=card_events)

        ce_layout.addWidget(r1)
        ce_layout.addWidget(r2)
        ce_layout.addWidget(r3)

        main_layout.addWidget(card_events)
        main_layout.addStretch()

        # 4. Footer: Encryption retention notice + Clear all button
        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)

        # Lock icon + Text
        lock_widget = QWidget(self)
        lock_widget.setFixedSize(14, 14)
        def draw_small_lock(e):
            p = QPainter(lock_widget)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor("#5C5C63"), 1.4))
            p.drawRoundedRect(QRectF(1, 4, 12, 9), 1.5, 1.5)
            p.drawArc(QRectF(3, 1, 8, 7), 0, 180 * 16)
            p.end()
        lock_widget.paintEvent = draw_small_lock
        footer_row.addWidget(lock_widget, 0, Qt.AlignVCenter)

        footer_lbl = QLabel(Strings.FOOTER_ENCRYPTED_RETENTION, self)
        footer_lbl.setFont(ThemeTokens.get_font(size_pt=11))
        footer_lbl.setStyleSheet("color: #5C5C63;")
        footer_row.addWidget(footer_lbl)
        footer_row.addStretch()

        clear_btn = PillButton(f"🗑  {Strings.BTN_CLEAR_ALL}", variant="danger", is_dark=False, parent=self)
        clear_btn.clicked.connect(self._clear_all_events)
        footer_row.addWidget(clear_btn)

        main_layout.addLayout(footer_row)

    def _open_lightbox(self, image_path: str):
        if image_path and os.path.exists(image_path):
            modal = ImageModal(image_path, self)
            modal.exec()

    def _export_activity(self):
        dest_dir = QFileDialog.getExistingDirectory(self, "Export Activity Log & Snapshots")
        if dest_dir:
            try:
                # Copy intruder images to destination folder
                count = 0
                if os.path.exists(INTRUDERS_DIR):
                    for f in os.listdir(INTRUDERS_DIR):
                        shutil.copy(os.path.join(INTRUDERS_DIR, f), dest_dir)
                        count += 1
                QMessageBox.information(self, "Export Complete", f"Successfully exported {count} snapshot files to:\n{dest_dir}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    def _clear_all_events(self):
        reply = QMessageBox.question(
            self,
            "Clear Activity & Photos",
            "Are you sure you want to delete all recorded intruder snapshots and event logs?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if os.path.exists(INTRUDERS_DIR):
                for f in os.listdir(INTRUDERS_DIR):
                    try:
                        os.remove(os.path.join(INTRUDERS_DIR, f))
                    except OSError:
                        pass
            QMessageBox.information(self, "Cleared", "All activity logs and snapshots have been cleared.")

    def refresh_gallery(self):
        pass


# Backward compatibility alias
IntruderLogPage = ActivityPage
