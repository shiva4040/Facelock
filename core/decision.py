"""
FaceLock Pure Decision Engine
Extracts presence evaluation, threshold comparison, strike accumulation,
decay, lens occlusion, and lock decisions into a deterministic, testable class.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class ActionType(Enum):
    NONE = auto()
    WARN = auto()               # Trigger strike warning HUD
    COUNTDOWN_LOCK = auto()     # Initiate countdown then lock
    IMMEDIATE_LOCK = auto()     # Lock instantly (tamper, absence timeout)


@dataclass
class FrameEvaluation:
    faces_count: int
    scores: List[float]
    lighting_val: float
    timestamp: float


@dataclass
class DecisionState:
    strikes: int = 0
    last_stranger_time: float = 0.0
    last_seen_owner_time: float = 0.0
    was_owner_present: bool = False
    had_enrolled_owner: bool = False
    owner_enrolled: bool = True
    is_paused: bool = False


@dataclass
class DecisionResult:
    action: ActionType
    hud_event: Optional[str]
    reason: str
    new_state: DecisionState
    highest_score: float = -1.0
    owner_present: bool = False
    stranger_present: bool = False
    snapshot_needed: bool = False


class DecisionEngine:
    """
    Pure decision engine for FaceLock security policies.
    Contains zero side-effects, GUI handles, or hardware locks.
    """

    @staticmethod
    def evaluate(
        frame: FrameEvaluation,
        state: DecisionState,
        match_threshold: float = 0.40,
        strikes_to_lock: int = 2,
        lock_on_stranger_with_owner: bool = True,
        lock_on_no_face_sec: int = 0,
        strike_decay_sec: float = 30.0,
    ) -> DecisionResult:
        # Clone state to avoid mutating caller's object directly
        new_state = DecisionState(
            strikes=state.strikes,
            last_stranger_time=state.last_stranger_time,
            last_seen_owner_time=state.last_seen_owner_time,
            was_owner_present=state.was_owner_present,
            had_enrolled_owner=state.had_enrolled_owner,
            owner_enrolled=state.owner_enrolled,
            is_paused=state.is_paused,
        )

        # 1. Strike decay: if elapsed time since last stranger exceeds decay window, reset strikes
        if new_state.strikes > 0 and new_state.last_stranger_time > 0 and (frame.timestamp - new_state.last_stranger_time > strike_decay_sec):
            new_state.strikes = 0

        # 2. Tamper check: if owner was previously enrolled but is suddenly missing while active
        if new_state.had_enrolled_owner and not new_state.owner_enrolled and not new_state.is_paused:
            return DecisionResult(
                action=ActionType.IMMEDIATE_LOCK,
                hud_event="locked",
                reason="Tamper Alert: Owner face data missing while protection active",
                new_state=new_state,
            )

        # 3. Idle if paused or no owner enrolled
        if new_state.is_paused or not new_state.owner_enrolled:
            return DecisionResult(
                action=ActionType.NONE,
                hud_event=None,
                reason="Monitoring paused or no owner enrolled",
                new_state=new_state,
            )

        # 4. Zero faces detected in frame
        if frame.faces_count == 0:
            # Lens blackout check (mean luminance < 5.0 after owner presence)
            if frame.lighting_val < 5.0 and new_state.was_owner_present:
                new_state.strikes += 1
                new_state.last_stranger_time = frame.timestamp
                if new_state.strikes >= strikes_to_lock:
                    return DecisionResult(
                        action=ActionType.COUNTDOWN_LOCK,
                        hud_event="locking_countdown",
                        reason=f"Lens blackout strike limit reached ({new_state.strikes}/{strikes_to_lock})",
                        new_state=new_state,
                        snapshot_needed=True,
                    )
                return DecisionResult(
                    action=ActionType.WARN,
                    hud_event="stranger_warning",
                    reason=f"Lens blackout strike {new_state.strikes}/{strikes_to_lock}",
                    new_state=new_state,
                )

            # Benign empty frame: notify owner away if previously present
            hud_event = None
            if new_state.was_owner_present:
                hud_event = "owner_left"
                new_state.was_owner_present = False

            # Absence timeout check
            if lock_on_no_face_sec > 0:
                absent_duration = frame.timestamp - new_state.last_seen_owner_time
                if absent_duration >= lock_on_no_face_sec:
                    return DecisionResult(
                        action=ActionType.IMMEDIATE_LOCK,
                        hud_event="locked",
                        reason=f"Absence timeout reached ({absent_duration:.1f}s)",
                        new_state=new_state,
                    )

            return DecisionResult(
                action=ActionType.NONE,
                hud_event=hud_event,
                reason="Area clear (zero faces)",
                new_state=new_state,
            )

        # 5. One or more faces detected
        highest_score = max(frame.scores) if frame.scores else -1.0
        owner_present = any(s >= match_threshold for s in frame.scores)
        stranger_present = any(s < match_threshold for s in frame.scores)

        strike_condition = stranger_present and (lock_on_stranger_with_owner or not owner_present)

        if strike_condition:
            new_state.strikes += 1
            new_state.last_stranger_time = frame.timestamp

            if new_state.strikes < strikes_to_lock:
                return DecisionResult(
                    action=ActionType.WARN,
                    hud_event="stranger_warning",
                    reason=f"Stranger strike {new_state.strikes}/{strikes_to_lock}",
                    new_state=new_state,
                    highest_score=highest_score,
                    owner_present=owner_present,
                    stranger_present=stranger_present,
                )
            else:
                return DecisionResult(
                    action=ActionType.COUNTDOWN_LOCK,
                    hud_event="locking_countdown",
                    reason=f"Stranger strike limit reached ({new_state.strikes}/{strikes_to_lock})",
                    new_state=new_state,
                    highest_score=highest_score,
                    owner_present=owner_present,
                    stranger_present=stranger_present,
                    snapshot_needed=True,
                )
        else:
            new_state.strikes = 0
            hud_event = None
            if owner_present:
                if not new_state.was_owner_present:
                    hud_event = "welcome"
                    new_state.was_owner_present = True
                new_state.last_seen_owner_time = frame.timestamp

            return DecisionResult(
                action=ActionType.NONE,
                hud_event=hud_event,
                reason="Owner verified" if owner_present else "Area permitted",
                new_state=new_state,
                highest_score=highest_score,
                owner_present=owner_present,
                stranger_present=stranger_present,
            )
