import cv2
import numpy as np
from recognition.detector import get_detector

def image_bytes_to_bgr(image_bytes: bytes):
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Không thể đọc ảnh.")
    return image

def get_faces_from_image(image_bgr):
    return get_detector().detect(image_bgr)

def get_single_embedding(image_bgr):
    faces = get_faces_from_image(image_bgr)

    if len(faces) == 0:
        raise ValueError("Không phát hiện khuôn mặt.")
    if len(faces) > 1:
        raise ValueError("Ảnh phải chỉ có một khuôn mặt.")

    face = faces[0]
    embedding = getattr(face, "normed_embedding", None)

    if embedding is None:
        embedding = getattr(face, "embedding", None)

    if embedding is None:
        raise ValueError("Không trích xuất được đặc trưng khuôn mặt.")

    return np.asarray(embedding, dtype=np.float32), face
