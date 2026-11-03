"""
Generate FaceLock assets: high-res app icons and subtle alert audio chimes.
"""
import os
import sys
import math
import struct
import wave
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QImage, QPainterPath

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(ICONS_DIR, exist_ok=True)
os.makedirs(SOUNDS_DIR, exist_ok=True)


def generate_icon(size: int = 256) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    s = size / 256.0

    # Squircle background (macOS App Icon style)
    bg_path = QPainterPath()
    bg_path.addRoundedRect(16 * s, 16 * s, 224 * s, 224 * s, 50 * s, 50 * s)

    # Dark blue-slate gradient background
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(22, 24, 30))
    p.drawPath(bg_path)

    # Hairline border
    p.setPen(QPen(QColor(255, 255, 255, 30), 2.0 * s))
    p.setBrush(Qt.NoBrush)
    p.drawPath(bg_path)

    # Outer Shield / Face biometric contour in macOS Accent Blue (#0A84FF)
    p.setPen(QPen(QColor(10, 132, 255), 7.0 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    # Shield path
    shield = QPainterPath()
    shield.moveTo(128 * s, 54 * s)
    shield.lineTo(192 * s, 76 * s)
    shield.lineTo(192 * s, 134 * s)
    shield.cubicTo(192 * s, 180 * s, 128 * s, 206 * s, 128 * s, 206 * s)
    shield.cubicTo(128 * s, 206 * s, 64 * s, 180 * s, 64 * s, 134 * s)
    shield.lineTo(64 * s, 76 * s)
    shield.closeSubpath()
    p.drawPath(shield)

    # Central Face Silhouette / Lock Shackle
    # Shackle
    p.setPen(QPen(QColor(255, 255, 255), 6.0 * s, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(QRectF(108 * s, 90 * s, 40 * s, 44 * s), 0, 180 * 16)

    # Lock Body
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255))
    p.drawRoundedRect(QRectF(100 * s, 114 * s, 56 * s, 44 * s), 8 * s, 8 * s)

    # Keyhole
    p.setBrush(QColor(22, 24, 30))
    p.drawEllipse(QRectF(124 * s, 128 * s, 8 * s, 8 * s))
    p.drawRect(QRectF(126 * s, 134 * s, 4 * s, 10 * s))

    p.end()
    return img


def create_wav(filename: str, frequencies: list, duration: float = 0.35, sample_rate: int = 44100):
    num_samples = int(sample_rate * duration)
    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        for i in range(num_samples):
            t = i / sample_rate
            # Harmonic decay envelope
            envelope = math.exp(-6.0 * (t / duration))

            val = 0.0
            for freq, amp in frequencies:
                val += amp * math.sin(2.0 * math.pi * freq * t)

            sample = int(val * envelope * 24000.0)
            sample = max(-32767, min(32767, sample))
            wav_file.writeframes(struct.pack("<h", sample))


if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Save PNG icon
    icon_png = os.path.join(ASSETS_DIR, "icon.png")
    img256 = generate_icon(256)
    img256.save(icon_png, "PNG")
    print(f"Generated {icon_png}")

    # 2. Save Windows ICO icon
    icon_ico = os.path.join(ASSETS_DIR, "icon.ico")
    img256.save(icon_ico, "ICO")
    print(f"Generated {icon_ico}")

    # 3. Generate audio files
    create_wav(os.path.join(SOUNDS_DIR, "welcome.wav"), [(523.25, 0.5), (659.25, 0.4), (783.99, 0.4)], duration=0.4)
    create_wav(os.path.join(SOUNDS_DIR, "warning.wav"), [(440.0, 0.6), (349.23, 0.5)], duration=0.3)
    create_wav(os.path.join(SOUNDS_DIR, "lock.wav"), [(220.0, 0.7), (110.0, 0.8)], duration=0.25)
    print("Generated sound files.")

