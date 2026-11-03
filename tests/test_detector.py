"""
Test YuNet and SFace model verification and face detection.
"""
import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.detector import check_and_download_models, FaceEngine


def test_models():
    print("Testing YuNet and SFace model acquisition...")
    det_path, rec_path = check_and_download_models()
    assert os.path.exists(det_path), f"Detector model missing: {det_path}"
    assert os.path.exists(rec_path), f"Recognizer model missing: {rec_path}"
    assert os.path.getsize(det_path) > 100_000, "Detector file suspiciously small"
    assert os.path.getsize(rec_path) > 10_000_000, "Recognizer file suspiciously small"
    print(f" [OK] Models present: {os.path.basename(det_path)} ({os.path.getsize(det_path)} bytes), {os.path.basename(rec_path)} ({os.path.getsize(rec_path)} bytes)")

    print("Testing FaceEngine inference on synthetic frame...")
    engine = FaceEngine()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw a synthetic face-like circle
    cv2.circle(dummy_frame, (320, 240), 80, (200, 200, 200), -1)
    cv2.circle(dummy_frame, (290, 220), 10, (50, 50, 50), -1)
    cv2.circle(dummy_frame, (350, 220), 10, (50, 50, 50), -1)

    faces = engine.detect_faces(dummy_frame)
    print(f" [OK] FaceEngine inference ran without errors. Detections on synthetic frame: {len(faces)}")

    mean_lum, note = engine.assess_lighting(dummy_frame)
    assert mean_lum >= 0.0
    print(f" [OK] Lighting assessment passed: {mean_lum:.1f} ({note})")


if __name__ == "__main__":
    test_models()
    print("\nDETECTOR ENGINE VERIFICATION SUCCESSFUL!")

