import cv2
from insightface.app import FaceAnalysis
from config import MODEL_NAME, USE_GPU, DET_SIZE, DET_THRESH

class FaceDetector:
    def __init__(self):
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if USE_GPU
            else ["CPUExecutionProvider"]
        )

        self.app = FaceAnalysis(
            name=MODEL_NAME,
            providers=providers,
        )

        # ctx_id=0 for CUDA, -1 for CPU.
        ctx_id = 0 if USE_GPU else -1
        self.app.prepare(
            ctx_id=ctx_id,
            det_size=DET_SIZE,
            det_thresh=DET_THRESH,
        )

    def detect(self, image_bgr):
        if image_bgr is None:
            raise ValueError("Ảnh không hợp lệ.")
        return self.app.get(image_bgr)

_detector = None

def get_detector():
    global _detector
    if _detector is None:
        _detector = FaceDetector()
    return _detector
