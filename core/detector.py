"""
FaceLock Face Engine
YuNet face detection + SFace recognition ONNX wrappers, lighting checks,
and intruder snapshot persistence.
"""
import os
import json
import time
import urllib.request
import ssl
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Callable

import cv2
import numpy as np

from core.config import MODELS_DIR, INTRUDERS_DIR

logger = logging.getLogger("facelock.detector")

DETECTOR_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
RECOGNIZER_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"


def check_and_download_models(progress_callback: Optional[Callable[[str, int], None]] = None) -> Tuple[str, str]:
    """
    Ensures YuNet and SFace models are present on disk, downloading them if necessary.
    
    Args:
        progress_callback: Optional callback receiving (model_name, percent_0_to_100).
        
    Returns:
        Tuple of (detector_path, recognizer_path)
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(INTRUDERS_DIR, exist_ok=True)

    det_path = os.path.join(MODELS_DIR, DETECTOR_FILE)
    rec_path = os.path.join(MODELS_DIR, RECOGNIZER_FILE)

    models = [
        (DETECTOR_FILE, DETECTOR_URL, det_path),
        (RECOGNIZER_FILE, RECOGNIZER_URL, rec_path),
    ]

    # Create unverified context if corporate proxy / cert issues arise
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for name, url, path in models:
        need_download = False
        if not os.path.exists(path):
            need_download = True
        elif os.path.getsize(path) < 100_000:
            logger.warning(f"File {path} exists but is suspiciously small (<100KB). Re-downloading.")
            need_download = True

        if need_download:
            logger.info(f"Downloading model {name} from {url}...")
            if progress_callback:
                progress_callback(name, 0)

            temp_path = path + ".tmp"
            try:
                opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
                with opener.open(url) as response, open(temp_path, "wb") as out_file:
                    total_size = int(response.info().get("Content-Length", -1))
                    downloaded = 0
                    chunk_size = 64 * 1024

                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(name, percent)

                if os.path.exists(path):
                    os.remove(path)
                os.rename(temp_path, path)
                logger.info(f"Successfully downloaded {name} ({os.path.getsize(path)} bytes).")
                if progress_callback:
                    progress_callback(name, 100)
            except Exception as e:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                logger.error(f"Failed to download model {name}: {e}")
                raise RuntimeError(f"Unable to download required AI model ({name}): {e}")

    return det_path, rec_path


class FaceEngine:
    """
    Thread-safe wrapper around YuNet (detection) and SFace (recognition).
    """

    def __init__(self, score_threshold: float = 0.80, nms_threshold: float = 0.3):
        det_path, rec_path = check_and_download_models()
        self.detector = cv2.FaceDetectorYN.create(
            model=det_path,
            config="",
            input_size=(320, 320),
            score_threshold=score_threshold,
            nms_threshold=nms_threshold,
            top_k=5000,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(model=rec_path, config="")
        logger.info("FaceEngine initialized successfully with YuNet and SFace.")

    def detect_faces(self, frame: np.ndarray) -> List[np.ndarray]:
        """
        Detects faces in frame.
        
        Returns:
            List of detected face vectors: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
        """
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        if faces is None:
            return []
        return [f for f in faces]

    def enhance_crop(self, crop: np.ndarray) -> np.ndarray:
        """Applies CLAHE on luminance channel for dynamic low-light / contrast compensation."""
        if crop is None or crop.size == 0:
            return crop
        try:
            lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        except Exception:
            return crop

    def extract_embedding(self, frame: np.ndarray, face: np.ndarray, boost_lighting: bool = True) -> np.ndarray:
        """
        Aligns and crops the face region, applies optional CLAHE contrast compensation,
        and extracts a 128-D feature embedding.
        """
        aligned = self.recognizer.alignCrop(frame, face)
        if boost_lighting:
            aligned = self.enhance_crop(aligned)
        feature = self.recognizer.feature(aligned)
        return feature

    def cosine_score(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """
        Calculates cosine similarity between two 128-D embeddings using SFace.
        Cosine score ranges typically from -1.0 to 1.0 (with >= 0.363 being SFace same-person threshold).
        """
        a = emb_a.reshape(1, -1).astype(np.float32)
        b = emb_b.reshape(1, -1).astype(np.float32)
        return float(self.recognizer.match(a, b, cv2.FaceRecognizerSF_FR_COSINE))

    def best_match_score(self, face_embedding: np.ndarray, owner_embeddings: np.ndarray) -> float:
        """
        Returns highest cosine match against any of the enrolled owner embeddings.
        """
        if owner_embeddings is None or len(owner_embeddings) == 0:
            return -1.0

        scores = [self.cosine_score(face_embedding, owner_emb) for owner_emb in owner_embeddings]
        return max(scores) if scores else -1.0

    @staticmethod
    def get_largest_face(faces: List[np.ndarray]) -> Optional[np.ndarray]:
        """Returns the face with the largest area (width * height)."""
        if not faces:
            return None
        return max(faces, key=lambda f: f[2] * f[3])

    @staticmethod
    def assess_lighting(frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]] = None) -> Tuple[float, str]:
        """
        Checks ambient / face illumination.
        
        Returns:
            (mean_luminance, status_description)
            Luminance is 0 (pitch black) to 255 (blown out).
        """
        if frame is None or frame.size == 0:
            return 0.0, "No image"

        if face_box:
            x, y, w, h = face_box
            h_f, w_f = frame.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, w_f - x), min(h, h_f - y)
            if w > 10 and h > 10:
                crop = frame[y:y+h, x:x+w]
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        mean_val = float(np.mean(gray))

        if mean_val < 45.0:
            return mean_val, "Low light: recognition accuracy may be reduced"
        elif mean_val > 220.0:
            return mean_val, "Overexposed: glare detected"
        else:
            return mean_val, "Good lighting"

    @staticmethod
    def save_intruder_snapshot(frame: np.ndarray, score: float = -1.0, lighting_note: str = "", threshold: float = 0.40) -> str:
        """
        Saves frame to ~/.facelock/intruders/intruder_YYYYMMDD_HHMMSS.jpg with companion JSON metadata.
        """
        os.makedirs(INTRUDERS_DIR, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intruder_{timestamp_str}.jpg"
        filepath = os.path.join(INTRUDERS_DIR, filename)
        cv2.imwrite(filepath, frame)

        # Save companion JSON metadata
        meta_path = os.path.splitext(filepath)[0] + ".json"
        meta = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": round(float(score), 3) if score >= 0 else None,
            "threshold": round(float(threshold), 3),
            "lighting": lighting_note or "Standard",
            "filename": filename,
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write metadata {meta_path}: {e}")

        logger.info(f"Saved intruder snapshot: {filepath} (score: {score:.2f})")
        return filepath

