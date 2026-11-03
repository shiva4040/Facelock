"""
FaceLock Guided Face Enrollment Worker
Executes step-by-step owner face capture with guided head pose prompts,
samples 20 diverse embeddings, encrypts them at rest, and streams live preview.
"""
import time
import logging
import platform
import cv2
import numpy as np
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core.config import AppConfig, OWNER_ENC_FILE
from core.crypto import encrypt_embeddings
from core.detector import FaceEngine
from core.events import events

logger = logging.getLogger("facelock.enroll")
IS_WINDOWS = platform.system() == "Windows"

PROMPT_STAGES = [
    (1, 4, "Look straight at the camera"),
    (5, 8, "Turn your head slightly to the left"),
    (9, 12, "Turn your head slightly to the right"),
    (13, 16, "Tilt your head slightly upward"),
    (17, 20, "Smile or change facial expression"),
]


def get_prompt_for_count(count: int) -> str:
    for start, end, text in PROMPT_STAGES:
        if start <= count <= end:
            return text
    return "Hold still..."


class EnrollWorker(QThread):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._running = True
        self._target_samples = 20
        self._engine: Optional[FaceEngine] = None

    def cancel(self) -> None:
        """Aborts the enrollment session."""
        self._running = False

    def run(self) -> None:
        logger.info("Starting guided enrollment worker.")
        events.enroll_progress.emit(0, self._target_samples, "Initializing camera and AI models...")

        try:
            self._engine = FaceEngine()
        except Exception as e:
            logger.error(f"Enrollment engine init error: {e}")
            events.enroll_finished.emit(False, f"Model error: {e}")
            return

        cap = None
        try:
            if IS_WINDOWS:
                cap = cv2.VideoCapture(self.config.camera_index, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(self.config.camera_index)

            if not cap.isOpened() and IS_WINDOWS:
                cap = cv2.VideoCapture(self.config.camera_index)
        except Exception as e:
            logger.error(f"Failed to open camera: {e}")
            events.enroll_finished.emit(False, f"Cannot open camera: {e}")
            return

        if not cap or not cap.isOpened():
            events.enroll_finished.emit(False, "Could not open camera device.")
            return

        embeds: List[np.ndarray] = []
        last_capture_time = 0.0

        try:
            while self._running and len(embeds) < self._target_samples:
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.04)
                    continue

                faces = self._engine.detect_faces(frame)
                now = time.time()
                prompt_text = get_prompt_for_count(len(embeds) + 1)
                preview_faces = []

                if len(faces) == 0:
                    status_note = "Position your face in the center ring"
                elif len(faces) > 1:
                    status_note = "Multiple faces detected — only one person allowed"
                    for f in faces:
                        x, y, w, h = map(int, f[:4])
                        preview_faces.append(((x, y, w, h), "Extra Face", 0.0, (40, 40, 240)))
                else:
                    face = faces[0]
                    x, y, w, h = map(int, face[:4])
                    preview_faces.append(((x, y, w, h), f"Sample {len(embeds)+1}/{self._target_samples}", 1.0, (40, 200, 60)))

                    # Check face size & capture rate
                    if w >= 60 and h >= 60:
                        status_note = prompt_text
                        if (now - last_capture_time) > 0.45:
                            emb = self._engine.extract_embedding(frame, face)[0]
                            embeds.append(emb)
                            last_capture_time = now
                            logger.info(f"Captured sample {len(embeds)}/{self._target_samples}")
                    else:
                        status_note = "Move a little closer to the camera"

                events.enroll_progress.emit(len(embeds), self._target_samples, status_note)
                events.preview_frame.emit(frame.copy(), preview_faces)
                time.sleep(0.03)

            if not self._running:
                logger.info("Enrollment cancelled by user.")
                events.enroll_finished.emit(False, "Enrollment cancelled.")
                return

            if len(embeds) >= self._target_samples:
                embeddings_array = np.array(embeds, dtype=np.float32)
                success = encrypt_embeddings(embeddings_array, OWNER_ENC_FILE)
                if success:
                    events.enroll_finished.emit(True, "Owner face enrolled successfully!")
                else:
                    events.enroll_finished.emit(False, "Failed to encrypt and save face data.")

        except Exception as e:
            logger.exception(f"Error during enrollment loop: {e}")
            events.enroll_finished.emit(False, f"Enrollment error: {e}")
        finally:
            if cap:
                cap.release()
            logger.info("Enrollment camera released.")

