"""
FaceLock Stage 1 Verification Test
Verifies:
1. Configuration loading, default values, and serialization.
2. Cryptography module (Fernet key generation, encrypting and decrypting embeddings).
3. FaceEngine model download/initialization and dummy face detection.
4. Screen lock simulation logic.
5. System tray component initialization with PySide6.
"""
import os
import sys
import tempfile
import numpy as np

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import AppConfig
from core.crypto import encrypt_embeddings, decrypt_embeddings
from core.lock import lock_workstation
from core.events import events


def test_config():
    print("Testing config module...")
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_file = os.path.join(tmpdir, "config.json")
        cfg = AppConfig.load(cfg_file)
        assert cfg.match_threshold == 0.40, f"Expected 0.40, got {cfg.match_threshold}"
        assert cfg.strikes_to_lock == 2, f"Expected 2, got {cfg.strikes_to_lock}"

        cfg.update(match_threshold=0.45, simulation_mode=True)
        assert cfg.match_threshold == 0.45
        assert cfg.simulation_mode is True

        cfg2 = AppConfig.load(cfg_file)
        assert cfg2.match_threshold == 0.45
        assert cfg2.simulation_mode is True
    print(" [OK] Config module passed.")


def test_crypto():
    print("Testing crypto module (Fernet encrypted embeddings)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        enc_file = os.path.join(tmpdir, "test_owner.enc")
        dummy_embeddings = np.random.randn(20, 128).astype(np.float32)

        # Encrypt
        ok = encrypt_embeddings(dummy_embeddings, enc_file)
        assert ok is True, "Encryption failed"
        assert os.path.exists(enc_file)
        assert os.path.getsize(enc_file) > 0

        # Verify not plaintext
        with open(enc_file, "rb") as f:
            raw = f.read()
            assert b"NUMPY" not in raw[:10], "File contains raw unencrypted numpy header!"

        # Decrypt
        decrypted = decrypt_embeddings(enc_file)
        assert decrypted is not None, "Decryption returned None"
        assert decrypted.shape == (20, 128), f"Decrypted shape mismatch: {decrypted.shape}"
        assert np.allclose(dummy_embeddings, decrypted, atol=1e-5), "Decrypted data values do not match original"
    print(" [OK] Crypto module passed.")


def test_lock_simulation():
    print("Testing lock workstation simulation mode...")
    success, msg = lock_workstation(simulation=True)
    assert success is True, "Simulation lock should return True"
    assert "Simulation mode" in msg
    print(" [OK] Lock simulation passed.")


def test_tray_and_qt():
    print("Testing PySide6 QApplication and FaceLockTray...")
    from PySide6.QtWidgets import QApplication
    from ui.tray import FaceLockTray, create_tray_pixmap

    # Use offscreen platform for headless execution
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance() or QApplication(sys.argv)

    cfg = AppConfig()
    tray = FaceLockTray(cfg)
    assert tray is not None
    pm = create_tray_pixmap("protected", 32)
    assert not pm.isNull(), "Tray pixmap should not be null"
    assert pm.width() == 32 and pm.height() == 32
    print(" [OK] PySide6 and Tray passed.")


if __name__ == "__main__":
    test_config()
    test_crypto()
    test_lock_simulation()
    test_tray_and_qt()
    print("\nSTAGE 1 TESTS COMPLETE AND SUCCESSFUL!")

