import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'database.sqlite'}"

# Recognition settings
MODEL_NAME = os.getenv("FACE_MODEL", "buffalo_l")
USE_GPU = os.getenv("USE_GPU", "0") == "1"
DET_SIZE = (640, 640)
DET_THRESH = float(os.getenv("DET_THRESH", "0.5"))

# IMPORTANT: This is a starting value only.
# Tune it with your own validation dataset in evaluation/evaluate.py.
RECOGNITION_THRESHOLD = float(os.getenv("RECOGNITION_THRESHOLD", "0.50"))

# Web
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB upload limit

FACES_DIR = BASE_DIR / "data" / "faces"
TEST_DIR = BASE_DIR / "data" / "test"
MODELS_DIR = BASE_DIR / "models"

for folder in (FACES_DIR, TEST_DIR, MODELS_DIR):
    folder.mkdir(parents=True, exist_ok=True)
