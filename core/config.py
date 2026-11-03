"""
FaceLock Configuration Management
Stores and manages user preferences in ~/.facelock/config.json.
Enforces HMAC-SHA256 signature verification against tamper attacks.
"""
import os
import json
import hmac
import shutil
import hashlib
import secrets
import logging
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional

from core.crypto import get_hmac_key

logger = logging.getLogger("facelock.config")

DEFAULT_BASE_DIR = os.path.join(os.path.expanduser("~"), ".facelock")
CONFIG_PATH = os.path.join(DEFAULT_BASE_DIR, "config.json")
MODELS_DIR = os.path.join(DEFAULT_BASE_DIR, "models")
INTRUDERS_DIR = os.path.join(DEFAULT_BASE_DIR, "intruders")
OWNER_ENC_FILE = os.path.join(DEFAULT_BASE_DIR, "owner.enc")
LOG_FILE = os.path.join(DEFAULT_BASE_DIR, "facelock.log")
LOCK_FILE = os.path.join(DEFAULT_BASE_DIR, "facelock.lock")
CLEAN_EXIT_MARKER = os.path.join(DEFAULT_BASE_DIR, ".clean_exit")


@dataclass
class AppConfig:
    camera_index: int = 0
    check_interval_sec: float = 3.0
    match_threshold: float = 0.40
    strikes_to_lock: int = 2
    strike_decay_sec: float = 30.0
    lock_on_no_face_sec: int = 0
    lock_on_stranger_with_owner: bool = True
    start_minimized: bool = False
    launch_at_login: bool = False
    simulation_mode: bool = False
    theme: str = "light"  # Light reference palette by default; dark remains opt-in.
    sound_enabled: bool = True
    notifications_enabled: bool = True
    live_preview: bool = False
    protection_enabled: bool = True
    watchdog_enabled: bool = True
    lock_mode: str = "native"  # "native" (OS lock) or "overlay" (FaceLock auto-unlock screen)
    overlay_pin_hash: str = ""
    overlay_pin_salt: str = ""
    pin_required: bool = False
    low_light_boost: bool = True
    auto_pause_on_video_call: bool = True
    _config_path: str = field(default=CONFIG_PATH, repr=False)

    def set_pin(self, pin: str) -> None:
        """Sets or clears the master PIN."""
        if not pin:
            self.overlay_pin_hash = ""
            self.overlay_pin_salt = ""
            self.pin_required = False
        else:
            self.overlay_pin_salt = secrets.token_hex(16)
            self.overlay_pin_hash = hashlib.pbkdf2_hmac(
                "sha256", pin.encode(), bytes.fromhex(self.overlay_pin_salt), 250_000
            ).hex()
            self.pin_required = True
        self.save()

    def verify_pin(self, pin: str) -> bool:
        """Verifies candidate PIN against the stored hash."""
        if not self.overlay_pin_hash:
            return True
        if self.overlay_pin_salt:
            candidate_hash = hashlib.pbkdf2_hmac(
                "sha256", pin.encode(), bytes.fromhex(self.overlay_pin_salt), 250_000
            ).hex()
        else:
            # Read older configurations so users can still verify and replace
            # a PIN saved by the previous fixed-salt implementation.
            candidate_hash = hashlib.sha256(("FaceLockMasterSalt_2026" + pin).encode()).hexdigest()
        return hmac.compare_digest(candidate_hash, self.overlay_pin_hash)

    @classmethod
    def load(cls, path: str = CONFIG_PATH) -> "AppConfig":
        """
        Loads configuration from disk, strictly verifying its HMAC signature.
        If signature is invalid, missing, or file is tampered, logs a critical
        tamper alert, backs up the tampered file, and restores defaults.
        """
        os.makedirs(DEFAULT_BASE_DIR, exist_ok=True)
        os.makedirs(MODELS_DIR, exist_ok=True)
        os.makedirs(INTRUDERS_DIR, exist_ok=True)

        if not os.path.exists(path):
            cfg = cls(_config_path=path)
            cfg.save(path)
            return cfg

        sig_path = path + ".sig"

        try:
            with open(path, "rb") as f:
                raw_bytes = f.read()

            # HMAC verification
            hmac_key = get_hmac_key()
            expected_sig = hmac.new(hmac_key, raw_bytes, hashlib.sha256).hexdigest()

            is_valid = False
            if os.path.exists(sig_path):
                with open(sig_path, "r", encoding="utf-8") as f:
                    stored_sig = f.read().strip()
                if hmac.compare_digest(stored_sig, expected_sig):
                    is_valid = True

            if not is_valid:
                logger.critical(
                    f"Tamper Alert: Config signature validation failed for {path}! "
                    "Rejecting untrusted file and reverting to safe factory defaults."
                )
                tampered_backup = path + ".tampered"
                try:
                    shutil.copyfile(path, tampered_backup)
                    logger.info(f"Backed up tampered config to {tampered_backup}")
                except Exception as ex:
                    logger.error(f"Failed to backup tampered config: {ex}")

                # Restore safe defaults and re-sign
                cfg = cls(_config_path=path)
                cfg.save(path)
                return cfg

            # Signature is valid - parse JSON
            data = json.loads(raw_bytes.decode("utf-8"))
            known_keys = {f.name for f in cls.__dataclass_fields__.values() if not f.name.startswith("_")}
            filtered = {k: v for k, v in data.items() if k in known_keys}

            # Security sanitization: enforce strict physical bounds on parameters
            if "match_threshold" in filtered:
                filtered["match_threshold"] = max(0.25, min(0.70, float(filtered["match_threshold"])))
            if "strikes_to_lock" in filtered:
                filtered["strikes_to_lock"] = max(1, min(10, int(filtered["strikes_to_lock"])))
            if "strike_decay_sec" in filtered:
                filtered["strike_decay_sec"] = max(5.0, min(300.0, float(filtered["strike_decay_sec"])))
            if "check_interval_sec" in filtered:
                filtered["check_interval_sec"] = max(1.0, min(30.0, float(filtered["check_interval_sec"])))

            cfg = cls(**filtered, _config_path=path)
            return cfg

        except Exception as e:
            logger.critical(f"Failed to read/parse config {path}, restoring safe defaults: {e}")
            cfg = cls(_config_path=path)
            cfg.save(path)
            return cfg

    def save(self, path: Optional[str] = None) -> None:
        """
        Saves current configuration and writes cryptographic HMAC signature.
        """
        target_path = path or self._config_path or CONFIG_PATH
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        try:
            data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
            raw_bytes = json.dumps(data, indent=2).encode("utf-8")

            with open(target_path, "wb") as f:
                f.write(raw_bytes)

            # Compute and persist signature
            hmac_key = get_hmac_key()
            sig = hmac.new(hmac_key, raw_bytes, hashlib.sha256).hexdigest()

            sig_path = target_path + ".sig"
            with open(sig_path, "w", encoding="utf-8") as f:
                f.write(sig)

            logger.debug(f"Saved and signed config to {target_path}")
        except Exception as e:
            logger.error(f"Failed to save signed config to {target_path}: {e}")

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k) and not k.startswith("_"):
                setattr(self, k, v)
        self.save()
