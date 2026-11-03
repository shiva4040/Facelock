"""
Phase 0 Regression & Security Unit Tests
Exercises real FaceLock production modules:
- DecisionEngine (pure evaluation, strike accumulation, decay, absence, shoulder-surfing, blackout)
- FaceLockWorker tamper suppression on user-initiated face data deletion
- Windows DPAPI and credential store round-trip without .key_fallback
- HMAC-SHA256 config signing and tamper rejection
- Independent process watchdog simulation
"""
import os
import sys
import json
import time
import pytest
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.decision import (
    DecisionEngine,
    DecisionState,
    FrameEvaluation,
    DecisionResult,
    ActionType,
)
from core.config import AppConfig, DEFAULT_BASE_DIR
from core.crypto import (
    encrypt_embeddings,
    decrypt_embeddings,
    get_hmac_key,
    delete_embeddings,
)
from core.watchdog import run_watchdog


# ============================================================================
# 1. Pure DecisionEngine Tests (Real Production Evaluation Logic)
# ============================================================================

class TestPureDecisionEngine:
    """Tests the real DecisionEngine.evaluate() with pure inputs and states."""

    def test_owner_recognized_resets_strikes_and_emits_welcome(self):
        frame = FrameEvaluation(
            faces_count=1,
            scores=[0.65],
            lighting_val=60.0,
            timestamp=100.0,
        )
        state = DecisionState(
            strikes=1,  # Had 1 strike previously
            was_owner_present=False,
            owner_enrolled=True,
            had_enrolled_owner=True,
        )
        res = DecisionEngine.evaluate(frame, state, match_threshold=0.40)
        assert res.action == ActionType.NONE
        assert res.hud_event == "welcome"
        assert res.new_state.strikes == 0
        assert res.new_state.was_owner_present is True
        assert res.new_state.last_seen_owner_time == 100.0
        assert res.owner_present is True
        assert res.stranger_present is False

    def test_threshold_exact_boundary_is_match(self):
        frame = FrameEvaluation(
            faces_count=1,
            scores=[0.40],  # Exactly on threshold
            lighting_val=50.0,
            timestamp=100.0,
        )
        state = DecisionState(owner_enrolled=True)
        res = DecisionEngine.evaluate(frame, state, match_threshold=0.40)
        assert res.action == ActionType.NONE
        assert res.owner_present is True
        assert res.stranger_present is False
        assert res.new_state.strikes == 0

    def test_threshold_epsilon_below_triggers_stranger_warning(self):
        frame = FrameEvaluation(
            faces_count=1,
            scores=[0.399999],  # Just below threshold
            lighting_val=50.0,
            timestamp=100.0,
        )
        state = DecisionState(strikes=0, owner_enrolled=True)
        res = DecisionEngine.evaluate(frame, state, match_threshold=0.40, strikes_to_lock=2)
        assert res.action == ActionType.WARN
        assert res.hud_event == "stranger_warning"
        assert res.new_state.strikes == 1
        assert res.new_state.last_stranger_time == 100.0
        assert res.owner_present is False
        assert res.stranger_present is True

    def test_consecutive_strangers_reach_strike_limit_triggers_countdown(self):
        frame = FrameEvaluation(
            faces_count=1,
            scores=[0.25],
            lighting_val=50.0,
            timestamp=103.0,
        )
        state = DecisionState(
            strikes=1,
            last_stranger_time=100.0,
            owner_enrolled=True,
        )
        res = DecisionEngine.evaluate(
            frame, state, match_threshold=0.40, strikes_to_lock=2, strike_decay_sec=30.0
        )
        assert res.action == ActionType.COUNTDOWN_LOCK
        assert res.hud_event == "locking_countdown"
        assert res.new_state.strikes == 2
        assert res.snapshot_needed is True

    def test_strike_decay_resets_stale_strikes(self):
        """
        Phase 0 Item 2: Strikes must decay after N seconds without a stranger,
        so a stray glance hours later cannot trigger a lock.
        """
        # Stranger at t=100.0 caused strike 1
        # Now at t=140.0 (> 30.0s decay window), next stranger arrives
        frame = FrameEvaluation(
            faces_count=1,
            scores=[0.20],
            lighting_val=50.0,
            timestamp=140.0,
        )
        state = DecisionState(
            strikes=1,
            last_stranger_time=100.0,  # 40s ago
            owner_enrolled=True,
        )
        res = DecisionEngine.evaluate(
            frame, state, match_threshold=0.40, strikes_to_lock=2, strike_decay_sec=30.0
        )
        # Stale strike decayed from 1 to 0, so this new stranger is Strike 1 (WARN), NOT Strike 2 (LOCK)!
        assert res.new_state.strikes == 1
        assert res.action == ActionType.WARN
        assert res.hud_event == "stranger_warning"

    def test_shoulder_surfing_policy_enabled(self):
        """Owner AND Stranger together in frame triggers strike when policy enabled."""
        frame = FrameEvaluation(
            faces_count=2,
            scores=[0.65, 0.20],  # Owner + Stranger
            lighting_val=60.0,
            timestamp=100.0,
        )
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(
            frame, state, match_threshold=0.40, lock_on_stranger_with_owner=True
        )
        assert res.owner_present is True
        assert res.stranger_present is True
        assert res.new_state.strikes == 1
        assert res.action == ActionType.WARN

    def test_shoulder_surfing_policy_disabled(self):
        """Owner AND Stranger together in frame is tolerated when policy disabled."""
        frame = FrameEvaluation(
            faces_count=2,
            scores=[0.65, 0.20],  # Owner + Stranger
            lighting_val=60.0,
            timestamp=100.0,
        )
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(
            frame, state, match_threshold=0.40, lock_on_stranger_with_owner=False
        )
        assert res.owner_present is True
        assert res.stranger_present is True
        assert res.new_state.strikes == 0
        assert res.action == ActionType.NONE

    def test_lens_blackout_when_owner_was_present(self):
        """Camera taped or blacked out right after owner was present triggers strike."""
        frame = FrameEvaluation(
            faces_count=0,
            scores=[],
            lighting_val=2.5,  # Dark / covered lens (< 5.0)
            timestamp=100.0,
        )
        state = DecisionState(strikes=0, was_owner_present=True, owner_enrolled=True)
        res = DecisionEngine.evaluate(frame, state, strikes_to_lock=2)
        assert res.action == ActionType.WARN
        assert res.new_state.strikes == 1
        assert "Lens blackout" in res.reason

    def test_absence_timeout_triggers_immediate_lock(self):
        """Owner absent past configured timeout triggers immediate lock."""
        frame = FrameEvaluation(
            faces_count=0,
            scores=[],
            lighting_val=50.0,
            timestamp=250.0,
        )
        state = DecisionState(
            strikes=0,
            was_owner_present=False,
            last_seen_owner_time=100.0,  # Absent for 150s
            owner_enrolled=True,
        )
        res = DecisionEngine.evaluate(frame, state, lock_on_no_face_sec=120)
        assert res.action == ActionType.IMMEDIATE_LOCK
        assert res.hud_event == "locked"
        assert "Absence timeout" in res.reason

    def test_tamper_detection_missing_owner_file_while_active(self):
        """If owner was enrolled but is suddenly missing while active, immediate lock fires."""
        frame = FrameEvaluation(
            faces_count=0,
            scores=[],
            lighting_val=50.0,
            timestamp=100.0,
        )
        state = DecisionState(
            had_enrolled_owner=True,
            owner_enrolled=False,  # Owner file gone!
            is_paused=False,
        )
        res = DecisionEngine.evaluate(frame, state)
        assert res.action == ActionType.IMMEDIATE_LOCK
        assert "Tamper Alert" in res.reason


# ============================================================================
# 2. Worker Owner Deletion & Tamper Flag Clearing Tests (Phase 0 Item 3)
# ============================================================================

class TestOwnerDataDeletionTamperSuppression:
    """Verifies that intentional deletion of owner data suppresses the tamper alarm."""

    def test_worker_on_owner_data_deleted_clears_flags(self):
        from core.worker import FaceLockWorker
        from PySide6.QtWidgets import QApplication

        # Ensure QApplication exists for QThread/signals
        app = QApplication.instance() or QApplication(sys.argv)

        cfg = AppConfig(simulation_mode=True)
        worker = FaceLockWorker(cfg)

        # Simulate state where owner was enrolled
        worker._had_enrolled_owner = True
        worker._owner_embeddings = np.random.randn(20, 128)
        worker._strikes = 1

        # User deletes owner data from UI
        worker.on_owner_data_deleted()

        assert worker._had_enrolled_owner is False
        assert worker._owner_embeddings is None
        assert worker._strikes == 0

        # Now evaluate next frame with deleted owner
        frame = FrameEvaluation(faces_count=0, scores=[], lighting_val=50.0, timestamp=100.0)
        state = DecisionState(
            had_enrolled_owner=worker._had_enrolled_owner,
            owner_enrolled=False,
            is_paused=False,
        )
        res = DecisionEngine.evaluate(frame, state)
        # MUST NOT trigger tamper lock!
        assert res.action == ActionType.NONE


# ============================================================================
# 3. Cryptography & Windows DPAPI Tests (Phase 0 Item 5)
# ============================================================================

class TestCryptographyDPAPI:
    """Verifies secure key storage via Windows DPAPI/Keyring and no .key_fallback."""

    def test_no_plaintext_fallback_file_on_disk(self):
        fallback_path = os.path.join(DEFAULT_BASE_DIR, ".key_fallback")
        assert not os.path.exists(fallback_path), "Security violation: .key_fallback must not exist!"

    def test_embeddings_encrypt_decrypt_roundtrip(self, tmp_path):
        target_path = str(tmp_path / "test_owner.enc")
        original = np.random.randn(20, 128).astype(np.float32)

        # Encrypt
        ok = encrypt_embeddings(original, target_path)
        assert ok is True
        assert os.path.exists(target_path)

        # File on disk must NOT be plain text / plain numpy magic
        with open(target_path, "rb") as f:
            raw_bytes = f.read()
        assert not raw_bytes.startswith(b"\x93NUMPY"), "Embeddings must be encrypted at rest!"

        # Decrypt
        decrypted = decrypt_embeddings(target_path)
        assert decrypted is not None
        assert decrypted.shape == (20, 128)
        assert np.allclose(original, decrypted)

        # Cleanup
        delete_embeddings(target_path)
        assert not os.path.exists(target_path)

    def test_hmac_key_derivation_deterministic_and_secure(self):
        k1 = get_hmac_key()
        k2 = get_hmac_key()
        assert isinstance(k1, bytes)
        assert len(k1) == 32
        assert k1 == k2


# ============================================================================
# 4. HMAC Configuration Signing & Tamper Rejection (Phase 0 Item 6)
# ============================================================================

class TestHMACConfigSigning:
    """Verifies cryptographic signature generation, verification, and tamper rejection."""

    def test_config_signed_and_tamper_detected(self, tmp_path):
        cfg_path = str(tmp_path / "config.json")
        sig_path = cfg_path + ".sig"

        # 1. Create and save configuration
        cfg = AppConfig(match_threshold=0.48, strike_decay_sec=20.0, _config_path=cfg_path)
        cfg.save(cfg_path)
        assert os.path.exists(cfg_path)
        assert os.path.exists(sig_path)

        # 2. Legitimate load succeeds
        loaded = AppConfig.load(cfg_path)
        assert loaded.match_threshold == 0.48
        assert loaded.strike_decay_sec == 20.0

        # 3. Attacker modifies config.json to lower threshold
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["match_threshold"] = 0.26  # modified
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # 4. AppConfig.load() MUST detect HMAC mismatch, reject tampered file, and restore defaults
        tampered_loaded = AppConfig.load(cfg_path)
        assert tampered_loaded.match_threshold == 0.40  # default restored!
        assert os.path.exists(cfg_path + ".tampered")   # tamper backup created for forensic audit


# ============================================================================
# 5. Watchdog Process Tests (Phase 0 Item 7)
# ============================================================================

class TestWatchdogBehavior:
    """Verifies watchdog logic with clean exit marker vs missing marker."""

    def test_watchdog_detects_clean_exit_with_marker(self, tmp_path):
        import subprocess
        marker = str(tmp_path / ".clean_exit")
        with open(marker, "w") as f:
            f.write("clean")

        # Spawn a short-lived target process that terminates after 0.2s
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
        clean_exit = run_watchdog(proc.pid, marker, simulation=True)
        assert clean_exit is True
        assert not os.path.exists(marker)

    def test_watchdog_detects_missing_marker_and_triggers_lock(self, tmp_path):
        import subprocess
        marker = str(tmp_path / ".clean_exit")
        if os.path.exists(marker):
            os.remove(marker)

        # Spawn a short-lived target process that terminates after 0.2s
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
        clean_exit = run_watchdog(proc.pid, marker, simulation=True)
        assert clean_exit is False
