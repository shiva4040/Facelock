"""
FaceLock Window Effects
Applies Windows 11 DWM Mica / Acrylic / Dark Mode attributes using ctypes dwmapi.
Falls back safely on older Windows versions or Linux.
"""
import sys
import ctypes
import platform
import logging

logger = logging.getLogger("facelock.effects")
IS_WINDOWS = platform.system() == "Windows"


def apply_mica_or_acrylic(hwnd: int, dark: bool = True) -> bool:
    """
    Applies Windows 11 backdrop effects (Mica / Acrylic) and dark mode window styling.
    """
    if not IS_WINDOWS:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi

        # 1. Immersive dark mode (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark_value = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark_value),
            ctypes.sizeof(dark_value),
        )

        # 2. Window corner preference (DWMWA_WINDOW_CORNER_PREFERENCE = 33, 2 = DWMWCP_ROUND)
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        corner_value = ctypes.c_int(2)  # Round corners (radius 12-14px)
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_value),
            ctypes.sizeof(corner_value),
        )

        # 3. Disable DWM backdrop. Qt paints the opaque macOS-style surface
        # itself; Mica behind translucent child widgets caused dark text
        # backing rectangles on some Windows builds.
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        backdrop_value = ctypes.c_int(2)  # DWMSBT_NONE
        res = dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop_value),
            ctypes.sizeof(backdrop_value),
        )

        logger.info("Windows 11 DWM backdrop effects applied successfully.")
        return res == 0

    except Exception as e:
        logger.debug(f"DWM effects not applied (likely pre-Win11 or headless): {e}")
        return False

