import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'local-dev-only-change-me')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str((ROOT / 'instance' / 'attendance.db').as_posix())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    UPLOAD_FOLDER = str(ROOT / 'uploads' / 'faces')
    MODEL_NAME = 'ArcFace'
    DETECTOR_BACKEND = 'retinaface'
    DISTANCE_METRIC = 'cosine'
    # Experimental threshold; validate on your own dataset before deployment.
    COSINE_THRESHOLD = float(os.environ.get('FACE_THRESHOLD', '0.68'))
