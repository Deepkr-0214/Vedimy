import base64
import io

# Optional dependencies — gracefully degraded if unavailable
try:
    import numpy as np
    import cv2
    _cv2_available = True
except ImportError:
    _cv2_available = False
    np = None

try:
    import face_recognition
    _fr_available = True
except ImportError:
    face_recognition = None
    _fr_available = False


class FaceService:
    def __init__(self, match_threshold=0.5):
        self.match_threshold = match_threshold

    def _base64_to_rgb_image(self, base64_str):
        if not _cv2_available:
            return None
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        img_data = base64.b64decode(base64_str)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def _bytes_to_rgb_image(self, image_bytes: bytes):
        """Decode raw image bytes (from file upload) to RGB numpy array."""
        if not _cv2_available:
            return None
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def encode_face(self, image_base64: str):
        if not _fr_available or not _cv2_available:
            return [0.0] * 128  # Stub
        rgb_img = self._base64_to_rgb_image(image_base64)
        if rgb_img is None:
            raise ValueError("Could not decode image")
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        if len(face_locations) == 0:
            raise ValueError("No face detected")
        if len(face_locations) > 1:
            raise ValueError("Multiple faces detected")
        encodings = face_recognition.face_encodings(rgb_img, face_locations)
        return encodings[0].tolist()

    def encode_face_from_bytes(self, image_bytes: bytes):
        """
        Encode faces from raw image bytes (e.g. uploaded file).
        Returns (list_of_encodings, thumbnail_bytes, error_str).
        Multiple faces in one image each produce a separate encoding.
        """
        if not _fr_available or not _cv2_available:
            return [[0.0] * 128], image_bytes, None  # Stub mode

        rgb_img = self._bytes_to_rgb_image(image_bytes)
        if rgb_img is None:
            return None, None, "Could not decode image"

        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        if len(face_locations) == 0:
            return None, None, "No face detected"

        results = []
        for loc in face_locations:
            enc = face_recognition.face_encodings(rgb_img, [loc])
            if enc:
                results.append(enc[0].tolist())

        if not results:
            return None, None, "Could not extract encoding"

        # Generate thumbnail (resize to 200px wide, JPEG bytes for storage)
        h, w = rgb_img.shape[:2]
        thumb_w = min(w, 200)
        thumb_h = int(h * thumb_w / w)
        bgr = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)
        thumb = cv2.resize(bgr, (thumb_w, thumb_h))
        _, thumb_bytes = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])

        return results, bytes(thumb_bytes), None

    def verify_face(self, image_base64: str, stored_encoding) -> dict:
        if not _fr_available or not _cv2_available:
            return {"match": True, "confidence": 1.0, "distance": 0.0}
        rgb_img = self._base64_to_rgb_image(image_base64)
        if rgb_img is None:
            return {"match": False, "confidence": 0.0, "distance": 1.0, "error": "decode_failed"}
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        if len(face_locations) == 0:
            return {"match": False, "confidence": 0.0, "distance": 1.0, "error": "no_face"}
        if len(face_locations) > 1:
            return {"match": False, "confidence": 0.0, "distance": 1.0, "error": "multiple_faces"}
        encodings = face_recognition.face_encodings(rgb_img, face_locations)
        current_encoding = encodings[0]
        distance = face_recognition.face_distance([np.array(stored_encoding)], current_encoding)[0]
        match = distance < self.match_threshold
        confidence = max(0.0, 1.0 - distance)
        return {"match": bool(match), "confidence": float(confidence), "distance": float(distance)}

    def verify_against_pool(self, image_base64: str, profile_pool: list) -> dict:
        """
        Match a live face image against a list of stored guest profiles.
        profile_pool: list of dicts with keys 'id', 'label', 'encoding' (list of floats).
        Returns best match result dict.
        """
        if not _fr_available or not _cv2_available:
            if profile_pool:
                return {"verified": True, "profile_id": profile_pool[0]["id"],
                        "label": profile_pool[0].get("label", ""), "confidence": 1.0,
                        "distance": 0.0, "error": None}
            return {"verified": False, "error": "no_profiles"}

        rgb_img = self._base64_to_rgb_image(image_base64)
        if rgb_img is None:
            return {"verified": False, "error": "decode_failed"}

        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        if len(face_locations) == 0:
            return {"verified": False, "error": "no_face"}
        if len(face_locations) > 1:
            return {"verified": False, "error": "multiple_faces"}

        live_encoding = face_recognition.face_encodings(rgb_img, face_locations)[0]
        known_encodings = [np.array(p["encoding"]) for p in profile_pool]
        distances = face_recognition.face_distance(known_encodings, live_encoding)

        best_idx = int(np.argmin(distances))
        best_dist = float(distances[best_idx])
        matched = best_dist < self.match_threshold

        if matched:
            best = profile_pool[best_idx]
            return {
                "verified": True,
                "profile_id": best["id"],
                "label": best.get("label", ""),
                "confidence": float(max(0.0, 1.0 - best_dist)),
                "distance": best_dist,
                "error": None
            }
        return {
            "verified": False,
            "error": "no_match",
            "confidence": float(max(0.0, 1.0 - best_dist)),
            "distance": best_dist
        }

    def detect_faces_count(self, image_base64: str) -> int:
        if not _fr_available or not _cv2_available:
            return 1
        rgb_img = self._base64_to_rgb_image(image_base64)
        if rgb_img is None:
            return 0
        face_locations = face_recognition.face_locations(rgb_img, model="hog")
        return len(face_locations)
