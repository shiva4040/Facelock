"""
FaceLock Event Bus
Decoupled Qt signals facilitating communication between the background
monitoring QThread, guided enrollment, HUD overlay, System Tray, and Main UI.
"""
from PySide6.QtCore import QObject, Signal
import numpy as np


class AppEventBus(QObject):
    # Overall protection status: status_code ("protected", "paused", "intruder", "absent"), description
    status_changed = Signal(str, str)

    # Periodic check result: metadata dict
    check_result = Signal(dict)

    # HUD popup request: state ("welcome", "owner_left", "stranger_warning", "locking_countdown", "locked"), title, subtitle, extra
    hud_trigger = Signal(str, str, str, dict)
    hud_cancel_countdown = Signal()

    # Intruder recorded: snapshot_path, highest_score, timestamp_str
    intruder_recorded = Signal(str, float, str)

    # Guided enrollment signals: current_step, total_steps, instruction_text
    enroll_progress = Signal(int, int, str)
    enroll_finished = Signal(bool, str)

    # Live camera preview stream: frame (BGR numpy array), face list [(box, label, score, color)]
    preview_frame = Signal(object, list)

    # Error handling
    camera_error = Signal(str)
    system_error = Signal(str)

    # Overlay Lock screen signals
    overlay_lock_requested = Signal()
    overlay_unlocked = Signal()

    # Config notification
    config_updated = Signal()

    # Main window shown/hidden/minimized so the activity can move to a floating
    # compact presentation while FaceLock is in the tray.
    window_visibility_changed = Signal(bool)

    # Biometrics management
    owner_data_cleared = Signal()


# Global event bus instance
events = AppEventBus()

