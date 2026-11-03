"""
Camera Feed & Face Bounding Box Viewport Widget
Renders live video frames with face tracking boxes, cosine scores,
and optional circular clipping for face enrollment.
"""
from typing import List, Tuple, Optional
import numpy as np
import cv2
from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import QPainter, QImage, QPixmap, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


class CameraView(QWidget):
    def __init__(self, circular_mask: bool = False, parent=None):
        super().__init__(parent)
        self.circular_mask = circular_mask
        self._pixmap: Optional[QPixmap] = None
        self._faces: List[Tuple] = []  # [(box, label, score, color)]
        self._placeholder_text = "Live preview paused"

    def set_placeholder(self, text: str):
        self._placeholder_text = text
        self.update()

    def update_frame(self, frame: np.ndarray, faces: Optional[List] = None):
        """
        Updates frame from OpenCV BGR numpy array.
        """
        if frame is None or frame.size == 0:
            return

        self._faces = faces or []
        h, w, ch = frame.shape
        bytes_per_line = ch * w

        # OpenCV is BGR; QImage Format_BGR888 is supported directly
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_BGR888)
        self._pixmap = QPixmap.fromImage(q_img)
        self.update()

    def clear(self):
        self._pixmap = None
        self._faces = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        # Clip path: circle or rounded rectangle
        clip_path = QPainterPath()
        if self.circular_mask:
            r = min(w, h)
            x_off = (w - r) / 2
            y_off = (h - r) / 2
            clip_path.addEllipse(x_off, y_off, r, r)
        else:
            clip_path.addRoundedRect(0, 0, w, h, 12, 12)

        painter.setClipPath(clip_path)

        if self._pixmap and not self._pixmap.isNull():
            # Scaled aspect ratio fill
            scaled_pm = self._pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            dx = (w - scaled_pm.width()) // 2
            dy = (h - scaled_pm.height()) // 2
            painter.drawPixmap(dx, dy, scaled_pm)

            # Draw face detection overlays
            orig_w = self._pixmap.width()
            orig_h = self._pixmap.height()
            scale_x = scaled_pm.width() / float(orig_w)
            scale_y = scaled_pm.height() / float(orig_h)

            for item in self._faces:
                try:
                    box, label, score, bgr_color = item
                    bx, by, bw, bh = box
                    # Map box to widget coords
                    rx = int(dx + bx * scale_x)
                    ry = int(dy + by * scale_y)
                    rw = int(bw * scale_x)
                    rh = int(bh * scale_y)

                    qc = QColor(bgr_color[2], bgr_color[1], bgr_color[0])  # BGR to RGB
                    painter.setPen(QPen(qc, 2.5))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(rx, ry, rw, rh, 6, 6)

                    # Label chip
                    if label:
                        painter.setFont(QFont('-apple-system, "SF Pro Text", "Segoe UI"', 10, QFont.Bold))
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QBrush(QColor(15, 15, 20, 200)))
                        chip_rect = QRect(rx, max(4, ry - 22), rw, 20)
                        painter.drawRoundedRect(chip_rect, 4, 4)

                        painter.setPen(qc)
                        painter.drawText(chip_rect, Qt.AlignCenter, label)
                except Exception:
                    continue

        else:
            # Placeholder dark slate background
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(28, 28, 34))
            painter.drawRect(0, 0, w, h)

            painter.setPen(QColor(120, 120, 125))
            painter.setFont(QFont('-apple-system, "SF Pro Text", "Segoe UI"', 12))
            painter.drawText(self.rect(), Qt.AlignCenter, self._placeholder_text)

        painter.end()

