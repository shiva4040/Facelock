"""
FaceLock Cryptography Module
Secures owner facial embeddings at rest using AES-128-CBC / Fernet encryption.

Key storage hierarchy:
1. OS Keyring (Windows Credential Manager / Secret Service)
2. Windows DPAPI (CryptProtectData) via Win32 crypt32.dll stored at ~/.facelock/master_key.dpapi
3. Non-Windows fallback: if keyring is unavailable, encryption at rest is disabled
   with a visible warning. No plaintext fallback files (.key_fallback) are stored.
"""
import io
import os
import sys
import base64
import hashlib
import logging
from typing import Optional
import numpy as np
from cryptography.fernet import Fernet
import keyring

logger = logging.getLogger("facelock.crypto")

SERVICE_NAME = "FaceLockSecureStorage"
KEY_USERNAME = "owner_embeddings_key"
DEFAULT_BASE_DIR = os.path.join(os.path.expanduser("~"), ".facelock")
DPAPI_KEY_FILE = os.path.join(DEFAULT_BASE_DIR, "master_key.dpapi")

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    def _dpapi_protect(data: bytes) -> bytes:
        """Encrypts bytes using Windows DPAPI (tied to current Windows user)."""
        in_blob = _DATA_BLOB(
            len(data),
            ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)),
        )
        out_blob = _DATA_BLOB()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if not _crypt32.CryptProtectData(
            ctypes.byref(in_blob), "FaceLockKey", None, None, None, 0x1, ctypes.byref(out_blob)
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            _kernel32.LocalFree(out_blob.pbData)

    def _dpapi_unprotect(data: bytes) -> bytes:
        """Decrypts bytes using Windows DPAPI."""
        in_blob = _DATA_BLOB(
            len(data),
            ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)),
        )
        out_blob = _DATA_BLOB()
        if not _crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0x1, ctypes.byref(out_blob)
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            _kernel32.LocalFree(out_blob.pbData)
else:
    def _dpapi_protect(data: bytes) -> bytes:
        raise NotImplementedError("DPAPI is only available on Windows")

    def _dpapi_unprotect(data: bytes) -> bytes:
        raise NotImplementedError("DPAPI is only available on Windows")


def _get_or_create_key() -> Optional[bytes]:
    """
    Retrieves the master encryption key from the OS keyring or DPAPI,
    generating and persisting a new one if not found.
    Returns None if encryption cannot be secured on non-Windows platforms.
    """
    # 1. Attempt OS Keyring
    try:
        key_str = keyring.get_password(SERVICE_NAME, KEY_USERNAME)
        if key_str:
            return key_str.encode("utf-8")
    except Exception as e:
        logger.warning(f"Keyring read failed: {e}")

    # 2. On Windows: Attempt DPAPI-protected file
    if IS_WINDOWS:
        if os.path.exists(DPAPI_KEY_FILE):
            try:
                with open(DPAPI_KEY_FILE, "rb") as f:
                    blob = f.read()
                raw_key = _dpapi_unprotect(blob)
                if len(raw_key) == 44:  # Valid Fernet key length
                    return raw_key
            except Exception as e:
                logger.error(f"Failed to unprotect DPAPI key file: {e}")

    # 3. Generate a brand new Fernet key
    new_key = Fernet.generate_key()
    saved = False

    # Try saving to keyring
    try:
        keyring.set_password(SERVICE_NAME, KEY_USERNAME, new_key.decode("utf-8"))
        saved = True
        logger.info("Saved new master key into OS credential store (Keyring).")
    except Exception as e:
        logger.warning(f"Could not save key into OS keyring: {e}")

    # If keyring failed, use DPAPI on Windows
    if not saved and IS_WINDOWS:
        try:
            os.makedirs(DEFAULT_BASE_DIR, exist_ok=True)
            protected_blob = _dpapi_protect(new_key)
            with open(DPAPI_KEY_FILE, "wb") as f:
                f.write(protected_blob)
            logger.info("Saved new master key encrypted via Windows DPAPI.")
            saved = True
        except Exception as e:
            logger.error(f"Failed to store key via Windows DPAPI: {e}")

    if not saved and not IS_WINDOWS:
        logger.warning(
            "OS Keyring is unavailable on this platform and DPAPI is Windows-only. "
            "Encryption at rest is disabled to prevent storing plaintext keys."
        )
        return None

    return new_key


def get_hmac_key() -> bytes:
    """
    Derives a 256-bit HMAC key for tamper detection and configuration signing.
    Uses the master key from DPAPI/keyring or a hardware/machine seed.
    """
    master_key = _get_or_create_key()
    if master_key:
        return hashlib.sha256(master_key + b"_facelock_hmac_salt_2026").digest()
    
    # Fallback machine-specific seed if no keyring/DPAPI available on non-Windows
    import uuid
    machine_id = str(uuid.getnode()).encode("utf-8")
    return hashlib.sha256(machine_id + b"_facelock_nonwin_unsecured_seed").digest()


def encrypt_embeddings(embeddings: np.ndarray, file_path: str) -> bool:
    """
    Encrypts a numpy array of embeddings and writes them to disk.
    If encryption is disabled on non-Windows, logs warning.
    """
    try:
        key = _get_or_create_key()
        buffer = io.BytesIO()
        np.save(buffer, embeddings.astype(np.float32))
        raw_bytes = buffer.getvalue()

        dirname = os.path.dirname(file_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        if key is not None:
            fernet = Fernet(key)
            encrypted_bytes = fernet.encrypt(raw_bytes)
            with open(file_path, "wb") as f:
                f.write(encrypted_bytes)
            logger.info(f"Encrypted and saved {len(embeddings)} face embeddings to {file_path}")
        else:
            logger.warning(f"Key unavailable; saving plaintext embeddings to {file_path}")
            with open(file_path, "wb") as f:
                f.write(raw_bytes)

        return True
    except Exception as e:
        logger.error(f"Failed to encrypt face embeddings: {e}")
        return False


def decrypt_embeddings(file_path: str) -> Optional[np.ndarray]:
    """
    Reads and decrypts face embeddings from disk.
    Returns np.ndarray or None if file doesn't exist or decryption fails.
    """
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            data = f.read()

        key = _get_or_create_key()
        if key is not None:
            fernet = Fernet(key)
            raw_bytes = fernet.decrypt(data)
        else:
            raw_bytes = data

        buffer = io.BytesIO(raw_bytes)
        embeddings = np.load(buffer)

        # Cleanup legacy unencrypted owner.npy if present
        legacy_plain = os.path.join(os.path.dirname(file_path), "owner.npy")
        if os.path.exists(legacy_plain):
            try:
                os.remove(legacy_plain)
                logger.info("Removed legacy unencrypted owner.npy from disk.")
            except OSError:
                pass

        return embeddings
    except Exception as e:
        logger.error(f"Failed to decrypt face embeddings from {file_path}: {e}")
        return None


def delete_embeddings(file_path: str) -> bool:
    """Safely deletes owner embeddings from disk."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted owner embeddings file {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting embeddings file {file_path}: {e}")
        return False
