"""
FaceLock Owner Face Enrollment Screen
Matches macOS Sonoma design specification exactly:
- Header: "Owner Face" + "Your face data is stored encrypted on this device only."
- Left Card:
  - 300px circular progress ring (blue #0066D6, 0-20 samples)
  - 252px circular dark camera viewport with dashed oval face guide
  - Prompt pill ("← Turn slightly left", #D5E5FA / #0B4FA8)
  - Sample caption ("12 of 20 samples")
  - Secondary pill button: "Cancel enrollment"
- Right Card (300px):
  - "Capture quality" checklist (Lighting, Face position, Sharpness, Only one face)
  - Guidance tip text
  - Danger pill button: "Delete face data" + caption "Removes every saved sample and turns protection off."
"""
import os
import cv2
import numpy as np
from PySide6.QtCore import Qt, QRectF, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QLabel, QMessageBox, QFrame
)

from core.config import AppConfig, OWNER_ENC_FILE
from core.crypto import delete_embeddings, decrypt_embeddings
from core.enroll import EnrollWorker
from core.events import events
from ui.theme import ThemeTokens
from ui.strings import Strings
from ui.components.card import MacCard
from ui.components.pill_button import PillButton
from ui.components.camera_view import CameraView


class CircularEnrollmentView(QWidget):
    """
    300px outer progress ring (light track, blue arc) with 252px inner circular
    camera viewport featuring a dashed oval face guide and silhouette.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)
        self._current_samples = 12
        self._max_samples = 20

        # Inner circular camera
        self.camera_widget = CameraView(circular_mask=True, parent=self)
        self.camera_widget.setFixedSize(252, 252)
        self.camera_widget.move(24, 24)

    def set_progress(self, current: int, total: int = 20):
        self._current_samples = current
        self._max_samples = total
        self.update()

    def update_frame(self, frame, faces):
        self.camera_widget.update_frame(frame, faces)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        thickness = 6.0
        rect = QRectF(thickness / 2.0, thickness / 2.0, w - thickness, h - thickness)

        # 1. Background light gray track circle
        painter.setPen(QPen(QColor("#E6E6EA"), thickness, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)

        # 2. Blue progress arc (#0066D6)
        fraction = max(0.0, min(1.0, float(self._current_samples) / float(self._max_samples or 1)))
        if fraction > 0.0:
            span_angle = int(-fraction * 360 * 16)
            start_angle = 90 * 16  # 12 o'clock
            painter.setPen(QPen(QColor("#0066D6"), thickness, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(rect, start_angle, span_angle)

        # 3. If camera has no active stream, draw subtle dashed oval guide on inner circle
        if not self.camera_widget._pixmap:
            cx = w / 2.0
            cy = h / 2.0
            painter.save()
            painter.translate(cx, cy)

            # Dark inner circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#2C2C30")))
            painter.drawEllipse(QRectF(-126, -126, 252, 252))

            # Head silhouette
            painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
            painter.drawEllipse(QRectF(-35, -55, 70, 75))
            painter.drawArc(QRectF(-65, 0, 130, 110), 30 * 16, 120 * 16)

            # Dashed white/gray oval face guide
            dash_pen = QPen(QColor("#A1A1A6"), 2.0, Qt.CustomDashLine)
            dash_pen.setDashPattern([4, 4])
            painter.setPen(dash_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(-52, -75, 104, 150))
            painter.restore()

        painter.end()


class QualityCheckRow(QWidget):
    """Single row in the Capture Quality checklist."""
    def __init__(self, label: str, default_status: str = "Good", is_good: bool = True, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 20px circular check indicator
        self.check_icon = QWidget(self)
        self.check_icon.setFixedSize(20, 20)
        self._is_good = is_good

        def paint_check(e):
            p = QPainter(self.check_icon)
            p.setRenderHint(QPainter.Antialiasing)
            bg = QColor("#E4F4EA") if self._is_good else QColor("#FFF1DC")
            fg = QColor("#1B7F45") if self._is_good else QColor("#8A5300")

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(bg))
            p.drawEllipse(0, 0, 20, 20)

            p.setPen(QPen(fg, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            if self._is_good:
                path = QPainterPath()
                path.moveTo(5.5, 10.0)
                path.lineTo(8.5, 13.0)
                path.lineTo(14.5, 7.0)
                p.drawPath(path)
            else:
                p.drawLine(10, 6, 10, 11)
                p.drawPoint(10, 14)
            p.end()

        self.check_icon.paintEvent = paint_check
        layout.addWidget(self.check_icon)

        # Label
        self.lbl = QLabel(label, self)
        self.lbl.setFont(ThemeTokens.get_font(size_pt=13, weight=500))
        self.lbl.setStyleSheet("color: #1D1D1F;")
        layout.addWidget(self.lbl)

        layout.addStretch()

        # Status text (green or amber)
        self.status_lbl = QLabel(default_status, self)
        self.status_lbl.setFont(ThemeTokens.get_font(size_pt=13, weight=500))
        self.status_lbl.setStyleSheet("color: #1B7F45; background-color: transparent;" if is_good else "color: #8A5300; background-color: transparent;")
        layout.addWidget(self.status_lbl)

    def set_quality(self, status: str, is_good: bool):
        self._is_good = is_good
        self.status_lbl.setText(status)
        self.status_lbl.setStyleSheet("color: #1B7F45; background-color: transparent;" if is_good else "color: #8A5300; background-color: transparent;")
        self.check_icon.update()


class OwnerFacePage(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._enroll_worker = None
        self._monitoring_worker = None
        self._resume_monitoring_after_enroll = False
        self._enrollment_success = False
        self._enrollment_pending = False
        self._current_samples = 0
        self._max_samples = 20

        self._build_ui()

        # Connect events
        events.enroll_progress.connect(self.on_enroll_progress)
        events.enroll_finished.connect(self.on_enroll_finished)
        events.preview_frame.connect(self.on_preview_frame)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(16)

        # 1. Header
        h_title = QLabel(Strings.OWNER_FACE_TITLE, self)
        h_title.setFont(ThemeTokens.get_font(size_pt=22, weight=600))
        h_title.setStyleSheet("color: #1D1D1F;")
        main_layout.addWidget(h_title)

        h_sub = QLabel(Strings.OWNER_FACE_SUBTITLE, self)
        h_sub.setFont(ThemeTokens.get_font(size_pt=13))
        h_sub.setStyleSheet("color: #5C5C63;")
        main_layout.addWidget(h_sub)

        # 2. Two-Column Card Layout
        cards_layout = QBoxLayout(QBoxLayout.LeftToRight)
        cards_layout.setSpacing(24)
        self.cards_layout = cards_layout

        # ====================================================================
        # LEFT CARD: 300px Progress Ring + Prompt Pill + Cancel Button
        # ====================================================================
        card_left = MacCard(is_hero=False, is_dark=False, parent=self)
        cl_layout = QVBoxLayout(card_left)
        cl_layout.setContentsMargins(24, 24, 24, 24)
        cl_layout.setSpacing(14)
        cl_layout.setAlignment(Qt.AlignCenter)

        # 300px Circular Enrollment View
        self.enroll_circle = CircularEnrollmentView(card_left)
        try:
            saved_embeddings = decrypt_embeddings(OWNER_ENC_FILE)
        except Exception:
            saved_embeddings = None
        has_profile = saved_embeddings is not None and len(saved_embeddings) > 0
        self._current_samples = self._max_samples if has_profile else 0
        self.enroll_circle.set_progress(self._current_samples, self._max_samples)
        cl_layout.addWidget(self.enroll_circle, 0, Qt.AlignCenter)

        # Prompt pill: "← Turn slightly left" (#D5E5FA background, #0B4FA8 text)
        initial_prompt = "Face profile is ready" if has_profile else "Start enrollment to begin"
        self.prompt_pill = QLabel(initial_prompt, card_left)
        self.prompt_pill.setFont(ThemeTokens.get_font(size_pt=13, weight=600))
        self.prompt_pill.setStyleSheet("""
            QLabel {
                background-color: #D5E5FA;
                color: #0B4FA8;
                border-radius: 14px;
                padding: 6px 18px;
            }
        """)
        self.prompt_pill.setAlignment(Qt.AlignCenter)
        cl_layout.addWidget(self.prompt_pill, 0, Qt.AlignCenter)

        # Sample count caption: "12 of 20 samples"
        self.samples_caption = QLabel(Strings.SAMPLE_PROGRESS_TEMPLATE.format(current=self._current_samples, total=self._max_samples), card_left)
        self.samples_caption.setFont(ThemeTokens.get_font(size_pt=13, weight=500, tabular=True))
        self.samples_caption.setStyleSheet("color: #5C5C63;")
        self.samples_caption.setAlignment(Qt.AlignCenter)
        cl_layout.addWidget(self.samples_caption, 0, Qt.AlignCenter)

        self.start_btn = PillButton(
            "Re-enroll face" if has_profile else "Start enrollment",
            variant="primary", is_dark=False, parent=card_left
        )
        self.start_btn.clicked.connect(self._start_enrollment)
        cl_layout.addWidget(self.start_btn, 0, Qt.AlignCenter)

        # Cancel enrollment is shown only during an active session.
        self.cancel_btn = PillButton(Strings.CANCEL_ENROLLMENT, variant="secondary", is_dark=False, parent=card_left)
        self.cancel_btn.clicked.connect(self._cancel_enrollment)
        self.cancel_btn.hide()
        cl_layout.addWidget(self.cancel_btn, 0, Qt.AlignCenter)

        cards_layout.addWidget(card_left, stretch=1)

        # ====================================================================
        # RIGHT CARD (300px): Capture Quality Checklist + Delete Face Data
        # ====================================================================
        card_right = MacCard(is_hero=False, is_dark=False, parent=self)
        card_right.setFixedWidth(300)
        cr_layout = QVBoxLayout(card_right)
        cr_layout.setContentsMargins(20, 20, 20, 20)
        cr_layout.setSpacing(12)

        q_title = QLabel(Strings.CAPTURE_QUALITY_TITLE, card_right)
        q_title.setFont(ThemeTokens.get_font(size_pt=14, weight=600))
        q_title.setStyleSheet("color: #1D1D1F;")
        cr_layout.addWidget(q_title)

        # 4 Quality Checklist Rows
        self.row_lighting = QualityCheckRow(Strings.QUALITY_LIGHTING, Strings.STATUS_GOOD, is_good=True, parent=card_right)
        self.row_position = QualityCheckRow(Strings.QUALITY_FACE_POSITION, Strings.STATUS_CENTERED, is_good=True, parent=card_right)
        self.row_sharpness = QualityCheckRow(Strings.QUALITY_SHARPNESS, Strings.STATUS_GOOD, is_good=True, parent=card_right)
        self.row_face_count = QualityCheckRow(Strings.QUALITY_ONLY_ONE_FACE, Strings.STATUS_YES, is_good=True, parent=card_right)

        cr_layout.addWidget(self.row_lighting)
        cr_layout.addWidget(self.row_position)
        cr_layout.addWidget(self.row_sharpness)
        cr_layout.addWidget(self.row_face_count)

        cr_layout.addSpacing(6)

        # Tip text below checklist
        tip_lbl = QLabel(Strings.ENROLL_TIP, card_right)
        tip_lbl.setFont(ThemeTokens.get_font(size_pt=11))
        tip_lbl.setStyleSheet("color: #5C5C63; line-height: 15px;")
        tip_lbl.setWordWrap(True)
        cr_layout.addWidget(tip_lbl)

        cr_layout.addStretch()

        # Delete Face Data Danger Pill Button
        self.delete_btn = PillButton(f"🗑  {Strings.DELETE_FACE_DATA}", variant="danger", is_dark=False, parent=card_right)
        self.delete_btn.clicked.connect(self._delete_face_data)
        cr_layout.addWidget(self.delete_btn)

        del_caption = QLabel(Strings.DELETE_FACE_DATA_DESC, card_right)
        del_caption.setFont(ThemeTokens.get_font(size_pt=11))
        del_caption.setStyleSheet("color: #5C5C63; line-height: 14px;")
        del_caption.setAlignment(Qt.AlignCenter)
        del_caption.setWordWrap(True)
        cr_layout.addWidget(del_caption)

        cards_layout.addWidget(card_right)
        main_layout.addLayout(cards_layout)

    def set_monitoring_worker(self, worker):
        self._monitoring_worker = worker

    def resizeEvent(self, event):
        super().resizeEvent(event)
        direction = QBoxLayout.TopToBottom if self.width() < 760 else QBoxLayout.LeftToRight
        if self.cards_layout.direction() != direction:
            self.cards_layout.setDirection(direction)

    def _start_enrollment(self):
        if self._enroll_worker is not None or self._enrollment_pending:
            return
        self._enrollment_pending = True
        worker = self._monitoring_worker
        self._resume_monitoring_after_enroll = bool(
            worker and worker.isRunning() and not worker._paused
        )
        self._enrollment_success = False
        self._current_samples = 0
        self.enroll_circle.set_progress(0, self._max_samples)
        self.samples_caption.setText(Strings.SAMPLE_PROGRESS_TEMPLATE.format(current=0, total=self._max_samples))
        self.prompt_pill.setText("Preparing camera…")
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.show()
        if self._resume_monitoring_after_enroll:
            worker.pause()
        QTimer.singleShot(800, self._launch_enrollment_worker)

    def _launch_enrollment_worker(self):
        if not self._enrollment_pending or self._enroll_worker is not None:
            return
        self._enroll_worker = EnrollWorker(self.config, self)
        self._enroll_worker.finished.connect(self._on_enroll_worker_stopped)
        self._enroll_worker.start()

    def _on_enroll_worker_stopped(self):
        self._enroll_worker = None
        self._enrollment_pending = False
        self.cancel_btn.hide()
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Re-enroll face" if self._enrollment_success else "Try enrollment again")
        if self._enrollment_success and self._monitoring_worker:
            self._monitoring_worker.reload_owner()
        if self._resume_monitoring_after_enroll and self._monitoring_worker:
            self._monitoring_worker.resume()
        self._resume_monitoring_after_enroll = False

    def _cancel_enrollment(self):
        if self._enroll_worker and self._enroll_worker.isRunning():
            self._enroll_worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.prompt_pill.setText("Stopping enrollment…")
        elif self._enrollment_pending:
            self._enrollment_pending = False
            self.cancel_btn.hide()
            self.start_btn.setEnabled(True)
            self.prompt_pill.setText("Enrollment cancelled")
            if self._resume_monitoring_after_enroll and self._monitoring_worker:
                self._monitoring_worker.resume()
            self._resume_monitoring_after_enroll = False

    def _delete_face_data(self):
        reply = QMessageBox.question(
            self,
            "Delete Face Profile",
            "Are you sure you want to delete your enrolled face data? FaceLock will not be able to guard your laptop until you re-enroll.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            delete_embeddings(OWNER_ENC_FILE)
            events.owner_data_cleared.emit()
            self._current_samples = 0
            self.enroll_circle.set_progress(0, 20)
            self.samples_caption.setText(Strings.SAMPLE_PROGRESS_TEMPLATE.format(current=0, total=20))
            self.prompt_pill.setText("No face enrolled")
            self.start_btn.setText("Start enrollment")
            events.status_changed.emit("paused", "No Owner Enrolled")
            QMessageBox.information(self, "Face Profile Deleted", "Your face embeddings have been securely removed.")

    def on_enroll_progress(self, current: int, total: int, instruction: str):
        self._current_samples = current
        self._max_samples = total
        self.enroll_circle.set_progress(current, total)
        self.samples_caption.setText(Strings.SAMPLE_PROGRESS_TEMPLATE.format(current=current, total=total))
        self.prompt_pill.setText(instruction)

    def on_enroll_finished(self, success: bool, message: str):
        self._enrollment_success = success
        if success:
            self._current_samples = self._max_samples
            self.enroll_circle.set_progress(self._max_samples, self._max_samples)
            self.samples_caption.setText(Strings.SAMPLE_PROGRESS_TEMPLATE.format(current=self._max_samples, total=self._max_samples))
            self.prompt_pill.setText("Enrollment complete")
            QMessageBox.information(self, "Enrollment Complete", "Your face profile has been securely saved and encrypted!")
        else:
            self.prompt_pill.setText(message)
            if "cancelled" not in message.lower():
                QMessageBox.warning(self, "Enrollment Ended", message)

    def on_preview_frame(self, frame, faces):
        self.enroll_circle.update_frame(frame, faces)

        # Compute real capture quality signals from frame
        if frame is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            mean_luma = float(np.mean(gray))
            laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # Lighting check
            is_luma_good = (mean_luma >= 40.0 and mean_luma <= 220.0)
            self.row_lighting.set_quality(Strings.STATUS_GOOD if is_luma_good else Strings.STATUS_LOW, is_luma_good)

            # Sharpness check
            is_sharp = (laplacian_var >= 50.0)
            self.row_sharpness.set_quality(Strings.STATUS_GOOD if is_sharp else Strings.STATUS_LOW, is_sharp)

            # Face position and count
            if faces:
                self.row_face_count.set_quality(Strings.STATUS_YES if len(faces) == 1 else Strings.STATUS_MULTIPLE, len(faces) == 1)
                f = faces[0]
                h_img, w_img = frame.shape[:2]
                fx, fy, fw, fh = f[:4]
                fcx = fx + fw / 2.0
                fcy = fy + fh / 2.0
                is_centered = (abs(fcx - w_img / 2.0) < w_img * 0.2 and abs(fcy - h_img / 2.0) < h_img * 0.2)
                self.row_position.set_quality(Strings.STATUS_CENTERED if is_centered else Strings.STATUS_OFF_CENTER, is_centered)
            else:
                self.row_face_count.set_quality("None", False)
                self.row_position.set_quality("None", False)
