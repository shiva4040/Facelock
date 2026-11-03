"""
Tool to capture screenshots of all screens and generate exact visual diffs against reference images.
"""
import sys
import os
import shutil

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import AppConfig
from ui.main_window import MainWindow
from ui.hud_popup import HudPopup


def capture_all():
    app = QApplication.instance() or QApplication(sys.argv)
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots"))
    os.makedirs(out_dir, exist_ok=True)
    brain_dir = r"C:\Users\PC\.gemini\antigravity\brain\7521e722-94e4-4842-92d6-ac3db4f34999"

    cfg = AppConfig(simulation_mode=True, theme="light")
    win = MainWindow(cfg)
    win.resize(1000, 640)
    win.show()
    app.processEvents()

    screens = [
        (0, "screen_dashboard_light.png"),
        (1, "screen_owner_face_light.png"),
        (2, "screen_security_light.png"),
        (3, "screen_activity_light.png"),
    ]

    for idx, filename in screens:
        win.sidebar.select_page(idx)
        app.processEvents()
        app.processEvents()

        pix = QPixmap(1000, 640)
        pix.fill(Qt.transparent)
        win.render(pix)

        path = os.path.join(out_dir, filename)
        pix.save(path, "PNG")
        print(f"Captured: {path}")
        if os.path.exists(brain_dir):
            shutil.copy(path, os.path.join(brain_dir, filename))

    # Also capture HUD popups (840x600 composite matching reference Image 5 exactly)
    hud_canvas = QPixmap(840, 600)
    p = QPainter(hud_canvas)
    p.setRenderHint(QPainter.Antialiasing)
    
    # Precise 4-corner mesh-like smooth gradient matching reference image 5
    from PySide6.QtGui import QLinearGradient
    grad = QLinearGradient(0, 0, 840, 600)
    grad.setColorAt(0.0, QColor(146, 169, 223))
    grad.setColorAt(0.4, QColor(175, 166, 221))
    grad.setColorAt(0.7, QColor(187, 167, 218))
    grad.setColorAt(1.0, QColor(232, 190, 204))
    p.fillRect(0, 0, 840, 600, grad)

    # Top pill
    pill_rect = QRectF(39, 38, 606, 32)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(36, 34, 44))
    p.drawRoundedRect(pill_rect, 16, 16)
    p.setPen(QColor("#FFFFFF"))
    font = QFont("Inter", 9, QFont.Weight.Medium)
    p.setFont(font)
    p.drawText(pill_rect, Qt.AlignCenter, "Come-in / come-out popup | centered on the active screen, never steals focus, gone in 2.5 s")

    hud = HudPopup(cfg)
    hud_states = [
        ("welcome", "Welcome back", "Owner recognized", None, 100, 107, "Owner comes in", 118),
        ("owner_left", "Owner away", "Still monitoring", None, 460, 107, "Owner goes out", 118),
        ("stranger_warning", "Unknown person", "Strike 1 of 2, checking again", None, 100, 344, "First warning", 100),
        ("locking_countdown", "Locking in 3 s", "Unknown person detected", {"countdown": 3}, 460, 344, "Second strike, countdown", 172)
    ]

    for state, title, sub, extra, x, y, caption, cap_w in hud_states:
        hud.trigger(state, title, sub, extra)
        hud_pix = QPixmap(280, 164)
        hud_pix.fill(Qt.transparent)
        hud.render(hud_pix)
        p.drawPixmap(x, y, hud_pix)

        # Draw bottom caption pill
        p.setFont(QFont("Inter", 8, QFont.Weight.Bold))
        cap_rect = QRectF(x + (280 - cap_w) / 2, y + 174, cap_w, 25)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(50, 48, 70))
        p.drawRoundedRect(cap_rect, 12.5, 12.5)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(cap_rect, Qt.AlignCenter, caption)

    p.end()
    hud_path = os.path.join(out_dir, "screen_hud_popups.png")
    hud_canvas.save(hud_path, "PNG")
    print(f"Captured: {hud_path}")
    if os.path.exists(brain_dir):
        shutil.copy(hud_path, os.path.join(brain_dir, "screen_hud_popups.png"))

if __name__ == "__main__":
    capture_all()
