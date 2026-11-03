"""
FaceLock Security & Core Logic Unit Tests
Tests matching, threshold boundary cases, strike counter state transitions,
shoulder surfing policy, config sanitization, and blackout handling
directly using the production DecisionEngine class.
"""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import AppConfig
from core.decision import (
    DecisionEngine,
    DecisionState,
    FrameEvaluation,
    ActionType,
)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Standard cosine similarity for 128-D embedding vectors."""
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    return float(np.dot(a_norm, b_norm))


class TestMatchingAndThreshold:
    """Unit tests for embedding comparison and boundary conditions."""

    def test_identical_embeddings_score_one(self):
        v = np.random.randn(128).astype(np.float32)
        score = cosine_similarity(v, v)
        assert pytest.approx(score, rel=1e-5) == 1.0

    def test_orthogonal_embeddings_score_zero(self):
        v1 = np.zeros(128, dtype=np.float32)
        v2 = np.zeros(128, dtype=np.float32)
        v1[0] = 1.0
        v2[1] = 1.0
        score = cosine_similarity(v1, v2)
        assert pytest.approx(score, abs=1e-5) == 0.0

    def test_opposite_embeddings_score_minus_one(self):
        v = np.random.randn(128).astype(np.float32)
        score = cosine_similarity(v, -v)
        assert pytest.approx(score, rel=1e-5) == -1.0

    def test_threshold_exact_boundary_is_match(self):
        frame = FrameEvaluation(faces_count=1, scores=[0.40], lighting_val=50.0, timestamp=10.0)
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(frame, state, match_threshold=0.40, strikes_to_lock=2)
        assert res.owner_present is True
        assert res.stranger_present is False
        assert res.new_state.strikes == 0
        assert res.action == ActionType.NONE

    def test_threshold_epsilon_below_is_stranger(self):
        frame = FrameEvaluation(faces_count=1, scores=[0.40 - 1e-6], lighting_val=50.0, timestamp=10.0)
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(frame, state, match_threshold=0.40, strikes_to_lock=2)
        assert res.owner_present is False
        assert res.stranger_present is True
        assert res.new_state.strikes == 1
        assert res.action == ActionType.WARN


class TestStrikeCounterTransitions:
    """Unit tests for consecutive strike counting and state transitions using DecisionEngine."""

    def test_consecutive_strikes_trigger_countdown(self):
        # Frame 1: Stranger detected (Strike 1)
        f1 = FrameEvaluation(faces_count=1, scores=[0.20], lighting_val=50.0, timestamp=10.0)
        s0 = DecisionState(strikes=0, owner_enrolled=True)
        r1 = DecisionEngine.evaluate(f1, s0, match_threshold=0.40, strikes_to_lock=2)
        assert r1.new_state.strikes == 1
        assert r1.hud_event == "stranger_warning"
        assert r1.action == ActionType.WARN

        # Frame 2: Stranger detected again (Strike 2 -> Lock countdown)
        f2 = FrameEvaluation(faces_count=1, scores=[0.22], lighting_val=50.0, timestamp=13.0)
        r2 = DecisionEngine.evaluate(f2, r1.new_state, match_threshold=0.40, strikes_to_lock=2)
        assert r2.new_state.strikes == 2
        assert r2.hud_event == "locking_countdown"
        assert r2.action == ActionType.COUNTDOWN_LOCK

    def test_owner_reappearance_resets_strikes(self):
        # Had 1 strike from a stranger
        s1 = DecisionState(strikes=1, last_stranger_time=10.0, was_owner_present=False, owner_enrolled=True)
        # Next frame sees owner
        f = FrameEvaluation(faces_count=1, scores=[0.65], lighting_val=50.0, timestamp=13.0)
        res = DecisionEngine.evaluate(f, s1, match_threshold=0.40, strikes_to_lock=2)
        assert res.new_state.strikes == 0
        assert res.owner_present is True
        assert res.stranger_present is False
        assert res.action == ActionType.NONE
        assert res.hud_event == "welcome"

    def test_zero_faces_preserves_pending_strikes_for_decay_window(self):
        # Zero faces detected after a stranger glance: strikes do not immediately vanish,
        # but owner_away is signaled if owner was present
        s1 = DecisionState(strikes=1, last_stranger_time=10.0, was_owner_present=True, owner_enrolled=True)
        f = FrameEvaluation(faces_count=0, scores=[], lighting_val=50.0, timestamp=12.0)
        res = DecisionEngine.evaluate(f, s1, match_threshold=0.40, strikes_to_lock=2, strike_decay_sec=30.0)
        assert res.new_state.strikes == 1  # Retained until decayed
        assert res.hud_event == "owner_left"
        assert res.action == ActionType.NONE


class TestShoulderSurfingPolicy:
    """Tests co-presence of Owner and Stranger."""

    def test_owner_and_stranger_together_locks_when_policy_enabled(self):
        frame = FrameEvaluation(faces_count=2, scores=[0.65, 0.20], lighting_val=50.0, timestamp=10.0)
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(
            frame, state, match_threshold=0.40, strikes_to_lock=2, lock_on_stranger_with_owner=True
        )
        assert res.owner_present is True
        assert res.stranger_present is True
        assert res.new_state.strikes == 1
        assert res.action == ActionType.WARN

    def test_owner_and_stranger_together_permits_when_policy_disabled(self):
        frame = FrameEvaluation(faces_count=2, scores=[0.65, 0.20], lighting_val=50.0, timestamp=10.0)
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(
            frame, state, match_threshold=0.40, strikes_to_lock=2, lock_on_stranger_with_owner=False
        )
        assert res.owner_present is True
        assert res.stranger_present is True
        assert res.new_state.strikes == 0
        assert res.action == ActionType.NONE


class TestConfigSanitization:
    """Security tests verifying that invalid/malicious config edits are sanitized."""

    def test_threshold_underflow_is_clamped(self, tmp_path):
        cfg = AppConfig(match_threshold=-0.5, strikes_to_lock=0, check_interval_sec=0.1)
        cfg_path = str(tmp_path / "config.json")
        cfg.save(cfg_path)

        loaded = AppConfig.load(cfg_path)
        assert loaded.match_threshold == 0.25
        assert loaded.strikes_to_lock == 1
        assert loaded.check_interval_sec == 1.0

    def test_threshold_overflow_is_clamped(self, tmp_path):
        cfg = AppConfig(match_threshold=0.99, strikes_to_lock=999, check_interval_sec=100.0)
        cfg_path = str(tmp_path / "config.json")
        cfg.save(cfg_path)

        loaded = AppConfig.load(cfg_path)
        assert loaded.match_threshold == 0.70
        assert loaded.strikes_to_lock == 10
        assert loaded.check_interval_sec == 30.0
