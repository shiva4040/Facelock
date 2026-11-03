"""
FaceLock Background Monitoring Worker
Runs in a dedicated QThread. Performs periodic camera frame grabs or continuous
live preview, runs YuNet + SFace recognition, evaluates security policies via
pure DecisionEngine, manages strikes with decay, emits Qt signals, and triggers
platform screen locking.
"""
import time
import logging
import platform
import cv2
import numpy as np
from typing import Optional, List, Dict
from PySide6.QtCore import QThread, Signal, Slot, QMutex

from core.config import AppConfig, OWNER_ENC_FILE
from core.crypto import decrypt_embeddings
from core.detector import FaceEngine
from core.decision import (
    DecisionEngine,
    DecisionState,
    FrameEvaluation,
    DecisionResult,
    ActionType,
)
from core.lock import lock_workstation
from core.events import events

logger = logging.getLogger("facelock.worker")
IS_WINDOWS = platform.system() == "Windows"


class FaceLockWorker(QThread):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._running = True
        self._paused = not config.protection_enabled
        self._mutex = QMutex()
        self._engine: Optional[FaceEngine] = None
        self._owner_embeddings: Optional[np.ndarray] = None
        self._owner_load_time: float = 0.0

        # State tracking (mirrors DecisionState)
        self._strikes = 0
        self._last_stranger_time: float = 0.0
        self._last_seen_owner_time: float = time.time()
        self._was_owner_present: bool = False
        self._countdown_cancelled: bool = False
        self._hud_last_fired: Dict[str, float] = {}
        self._camera_busy_notified: bool = False
        self._had_enrolled_owner: bool = False

        # Connect event to clear tamper flag when user deletes face data
        events.owner_data_cleared.connect(self.on_owner_data_deleted)

    @Slot()
    def on_owner_data_deleted(self) -> None:
        """Invoked when user intentionally deletes owner face data from the UI."""
        self._had_enrolled_owner = False
        self._owner_embeddings = None
        self._strikes = 0
        self._was_owner_present = False
        logger.info("Owner face data deleted by user: tamper alarm suppressed.")

    def reload_owner(self) -> bool:
        """Reloads decrypted owner embeddings from disk."""
        self._owner_embeddings = decrypt_embeddings(OWNER_ENC_FILE)
        if self._owner_embeddings is not None and len(self._owner_embeddings) > 0:
            logger.info(f"Loaded {len(self._owner_embeddings)} owner embeddings.")
            self._had_enrolled_owner = True
            return True
        else:
            logger.warning("No owner embeddings found or decryption failed.")
            self._owner_embeddings = None
            return False

    def pause(self) -> None:
        """Pauses face monitoring."""
        self._paused = True
        events.status_changed.emit("paused", "Monitoring Paused")

    def resume(self) -> None:
        """Resumes face monitoring."""
        self._strikes = 0
        self._paused = False
        self._last_seen_owner_time = time.time()
        events.status_changed.emit("protected", "Monitoring Active")

    def cancel_countdown(self) -> None:
        """Cancels an active lock countdown."""
        self._countdown_cancelled = True
        self._strikes = 0
        logger.info("Active lock countdown cancelled by user.")

    def stop(self) -> None:
        """Stops the worker thread cleanly."""
        self._running = False
        self.wait(2000)

    def _open_camera(self) -> Optional[cv2.VideoCapture]:
        """Opens camera using platform-optimized backend."""
        idx = self.config.camera_index
        cap = None
        try:
            if IS_WINDOWS:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(idx)

            if not cap.isOpened():
                if IS_WINDOWS:
                    # Fallback to default backend
                    cap = cv2.VideoCapture(idx)
        except Exception as e:
            logger.error(f"Error opening camera {idx}: {e}")
            events.camera_error.emit(f"Failed to open camera: {e}")
            return None

        if not cap or not cap.isOpened():
            if not self._camera_busy_notified:
                logger.info(f"Camera device {idx} currently unavailable or in use by another app.")
                events.status_changed.emit("paused", "Camera Busy (Video Call Active)")
                self._camera_busy_notified = True
            return None

        if self._camera_busy_notified:
            logger.info(f"Camera device {idx} reacquired.")
            events.status_changed.emit("protected", "Guarding Active")
            self._camera_busy_notified = False

        return cap

    def _grab_single_frame(self, warmup: int = 4) -> Optional[np.ndarray]:
        """Opens camera, grabs a warmed-up frame, and releases camera immediately."""
        cap = self._open_camera()
        if cap is None:
            return None
        frame = None
        try:
            for _ in range(warmup):
                ok, f = cap.read()
                if ok:
                    frame = f
                else:
                    time.sleep(0.03)
            return frame
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None
        finally:
            cap.release()

    def _trigger_hud_debounced(self, state: str, title: str, subtitle: str, extra: dict = None, debounce_sec: float = 10.0) -> None:
        """Fires a HUD notification if debounce interval has elapsed."""
        if not self.config.notifications_enabled:
            return

        now = time.time()
        last_time = self._hud_last_fired.get(state, 0.0)
        # Always allow countdown & locked without 10s throttle
        if state not in ("locking_countdown", "locked") and (now - last_time < debounce_sec):
            return

        self._hud_last_fired[state] = now
        events.hud_trigger.emit(state, title, subtitle, extra or {})

    def run(self) -> None:
        logger.info("FaceLock background monitoring thread started.")
        try:
            self._engine = FaceEngine()
        except Exception as e:
            logger.error(f"FaceEngine initialization failed: {e}")
            events.system_error.emit(f"Failed to initialize AI models: {e}")
            return

        self.reload_owner()

        last_check_time = 0.0
        active_cap: Optional[cv2.VideoCapture] = None

        while self._running:
            try:
                # If paused or no owner enrolled, idle (or alert if enrolled owner file was deleted while guarding)
                if self._paused or self._owner_embeddings is None:
                    if self._had_enrolled_owner and not self._paused:
                        logger.critical("Owner face file missing while guarding! Locking workstation for safety.")
                        self._trigger_hud_debounced("locked", "Security Alert", "Biometric file missing", debounce_sec=0.0)
                        lock_workstation(simulation=self.config.simulation_mode, lock_mode=self.config.lock_mode)
                        events.status_changed.emit("paused", "Tamper Alert: Face File Missing")
                    if active_cap is not None:
                        active_cap.release()
                        active_cap = None
                    time.sleep(1.0)
                    continue

                now = time.time()

                # Continuous Live Preview Mode vs Periodic Check Cycle
                if self.config.live_preview:
                    if active_cap is None:
                        active_cap = self._open_camera()
                        if active_cap is None:
                            time.sleep(1.0)
                            continue

                    ok, frame = active_cap.read()
                    if not ok or frame is None:
                        time.sleep(0.05)
                        continue

                    # Process face detections & embeddings on the frame
                    self._process_frame(frame, is_live_stream=True)
                    time.sleep(0.03)  # ~30 FPS throttle
                else:
                    # Release active cap if previously opened
                    if active_cap is not None:
                        active_cap.release()
                        active_cap = None

                    # Wait until next check interval
                    elapsed = now - last_check_time
                    if elapsed < self.config.check_interval_sec:
                        time.sleep(0.1)
                        continue

                    last_check_time = time.time()
                    frame = self._grab_single_frame()
                    if frame is None:
                        logger.warning("Frame grab returned empty.")
                        time.sleep(1.0)
                        continue

                    self._process_frame(frame, is_live_stream=False)

            except Exception as e:
                logger.exception(f"Unexpected error in FaceLock monitoring loop: {e}")
                time.sleep(1.0)

        if active_cap is not None:
            active_cap.release()
        logger.info("FaceLock monitoring thread terminated gracefully.")

    def _process_frame(self, frame: np.ndarray, is_live_stream: bool) -> None:
        """Performs face detection, verification, and triggers security actions via pure DecisionEngine."""
        faces = self._engine.detect_faces(frame)
        lighting_val, lighting_note = self._engine.assess_lighting(frame)

        preview_faces = []
        scores: List[float] = []

        now = time.time()
        for f in faces:
            emb = self._engine.extract_embedding(frame, f)
            score = self._engine.best_match_score(emb, self._owner_embeddings) if self._owner_embeddings is not None else 0.0
            scores.append(score)

            is_match = score >= self.config.match_threshold
            x, y, w, h = map(int, f[:4])
            label = f"Owner ({score:.2f})" if is_match else f"Unknown ({score:.2f})"
            color = (40, 200, 60) if is_match else (40, 60, 240)  # Green / Red BGR
            preview_faces.append(((x, y, w, h), label, score, color))

        # Build pure inputs for DecisionEngine
        frame_eval = FrameEvaluation(
            faces_count=len(faces),
            scores=scores,
            lighting_val=lighting_val,
            timestamp=now,
        )

        state = DecisionState(
            strikes=self._strikes,
            last_stranger_time=self._last_stranger_time,
            last_seen_owner_time=self._last_seen_owner_time,
            was_owner_present=self._was_owner_present,
            had_enrolled_owner=self._had_enrolled_owner,
            owner_enrolled=self._owner_embeddings is not None and len(self._owner_embeddings) > 0,
            is_paused=self._paused,
        )

        decision = DecisionEngine.evaluate(
            frame=frame_eval,
            state=state,
            match_threshold=self.config.match_threshold,
            strikes_to_lock=self.config.strikes_to_lock,
            lock_on_stranger_with_owner=self.config.lock_on_stranger_with_owner,
            lock_on_no_face_sec=self.config.lock_on_no_face_sec,
            strike_decay_sec=getattr(self.config, "strike_decay_sec", 30.0),
        )

        # Update worker state directly from pure decision result
        self._strikes = decision.new_state.strikes
        self._last_stranger_time = decision.new_state.last_stranger_time
        self._last_seen_owner_time = decision.new_state.last_seen_owner_time
        self._was_owner_present = decision.new_state.was_owner_present

        # Dispatch UI signals and hardware actions
        if decision.action == ActionType.COUNTDOWN_LOCK:
            logger.warning(f"Lock countdown triggered: {decision.reason}")
            events.status_changed.emit("intruder", f"Stranger Detected ({self._strikes}/{self.config.strikes_to_lock})")
            self._handle_strike_countdown(frame, decision.highest_score)

        elif decision.action == ActionType.IMMEDIATE_LOCK:
            logger.critical(f"Immediate lock executed: {decision.reason}")
            self._trigger_hud_debounced("locked", "Screen Locked", decision.reason, debounce_sec=0.0)
            lock_workstation(simulation=self.config.simulation_mode, lock_mode=self.config.lock_mode)

        elif decision.action == ActionType.WARN:
            logger.warning(f"Warning issued: {decision.reason}")
            events.status_changed.emit("intruder", f"Stranger Detected ({self._strikes}/{self.config.strikes_to_lock})")
            self._trigger_hud_debounced(
                "stranger_warning",
                "Unknown Person Detected",
                f"Strike {self._strikes} of {self.config.strikes_to_lock}",
                debounce_sec=2.0
            )

        else:  # ActionType.NONE
            if decision.hud_event == "welcome":
                self._trigger_hud_debounced("welcome", "Welcome Back", "Owner recognized")
                events.status_changed.emit("protected", "Protected - Owner Present")
            elif decision.hud_event == "owner_left":
                self._trigger_hud_debounced("owner_left", "Owner Away", "Monitoring active")
                events.status_changed.emit("protected", "Guarding (Area Clear)")
            elif decision.owner_present:
                events.status_changed.emit("protected", "Protected - Owner Present")
            else:
                events.status_changed.emit("protected", "Guarding (Area Clear)")

        # Emit preview frame if live preview is enabled
        if is_live_stream:
            events.preview_frame.emit(frame.copy(), preview_faces)

        # Emit check result metadata
        events.check_result.emit({
            "timestamp": now,
            "faces_count": len(faces),
            "owner_present": decision.owner_present,
            "stranger_present": decision.stranger_present,
            "highest_score": decision.highest_score,
            "strikes": self._strikes,
            "max_strikes": self.config.strikes_to_lock,
            "lighting_val": lighting_val,
            "lighting_note": lighting_note,
        })

    def _handle_strike_countdown(self, frame: np.ndarray, score: float) -> None:
        """Handles 3-second countdown before locking, giving user chance to cancel."""
        self._countdown_cancelled = False
        countdown_secs = 3

        logger.info(f"Starting {countdown_secs}s countdown to lock...")
        self._trigger_hud_debounced(
            "locking_countdown",
            f"Locking in {countdown_secs}s...",
            "Stranger confirmed at laptop",
            {"countdown": countdown_secs},
            debounce_sec=0.0
        )

        for remaining in range(countdown_secs, 0, -1):
            if self._countdown_cancelled or not self._running:
                logger.info("Countdown aborted.")
                self._strikes = 0
                return
            time.sleep(1.0)

        if self._countdown_cancelled or not self._running:
            self._strikes = 0
            return

        # Snapshot intruder with metadata
        snapshot_path = self._engine.save_intruder_snapshot(
            frame, score=score, threshold=self.config.match_threshold
        )
        events.intruder_recorded.emit(snapshot_path, score, time.strftime("%Y-%m-%d %H:%M:%S"))

        # Trigger HUD "Locked"
        self._trigger_hud_debounced("locked", "Screen Locked", "Laptop locked for security", debounce_sec=0.0)

        # Execute workstation lock (native OS or FaceLock Overlay)
        lock_workstation(simulation=self.config.simulation_mode, lock_mode=self.config.lock_mode)
        self._strikes = 0
        time.sleep(5.0)  # Post-lock cooling period
