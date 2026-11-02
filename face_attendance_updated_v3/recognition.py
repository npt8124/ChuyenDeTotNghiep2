import json
import numpy as np
from deepface import DeepFace
from config import Config
from models import FaceSample, Student

def embeddings(image):
    result = DeepFace.represent(
        img_path=image, model_name=Config.MODEL_NAME,
        detector_backend=Config.DETECTOR_BACKEND,
        enforce_detection=True, align=True
    )
    return result

def encode_one(image):
    faces = embeddings(image)
    if len(faces) != 1:
        raise ValueError('Ảnh đăng ký phải chứa đúng một khuôn mặt.')
    return faces[0]['embedding']

def cosine_distance(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 1 - float(np.dot(a, b) / denom) if denom else 1.0

def check_liveness(image):
    """Check a live camera frame with DeepFace FasNet anti-spoofing.

    This is intentionally called only by the realtime attendance API, never
    by the student face-enrollment routes.
    """
    try:
        detected = DeepFace.extract_faces(
            img_path=image,
            detector_backend=Config.DETECTOR_BACKEND,
            enforce_detection=True,
            align=True,
            anti_spoofing=True,
        )
    except Exception as exc:
        raise RuntimeError(
            'Không chạy được Face Anti-Spoofing. Kiểm tra phiên bản DeepFace, '
            'kết nối tải trọng số FasNet và log máy chủ.'
        ) from exc

    if len(detected) != 1:
        return {'label': 'no_face' if not detected else 'multiple_faces',
                'message': 'Không phát hiện khuôn mặt.' if not detected
                else 'Chỉ để một người trước camera.'}

    face = detected[0]
    is_real = face.get('is_real')
    score = face.get('antispoof_score')
    if is_real is None:
        raise RuntimeError('DeepFace không trả về kết quả Anti-Spoofing hợp lệ.')
    if not bool(is_real):
        return {'label': 'spoof',
                'message': 'Không vượt qua kiểm tra người thật. Vui lòng dùng khuôn mặt trực tiếp trước camera.',
                'antispoof_score': round(float(score), 4) if score is not None else None}
    return {'label': 'live',
            'antispoof_score': round(float(score), 4) if score is not None else None}


def recognize(image, class_id, anti_spoofing=False):
    liveness = None
    if anti_spoofing:
        liveness = check_liveness(image)
        if liveness.get('label') != 'live':
            return liveness
    samples = (FaceSample.query.join(Student)
               .filter(Student.class_id == class_id).all())
    if not samples:
        return {'label': 'no_enrollment', 'message': 'Lớp chưa có dữ liệu khuôn mặt.'}
    faces = embeddings(image)
    if not faces:
        return {'label': 'no_face', 'message': 'Không phát hiện khuôn mặt.'}
    # For classroom demo: reject multi-face frames to avoid ambiguous matching.
    if len(faces) != 1:
        return {'label': 'multiple_faces', 'message': 'Chỉ để một người trước camera.'}
    query = faces[0]['embedding']
    per_student = {}
    for sample in samples:
        distance = cosine_distance(query, json.loads(sample.embedding_json))
        sid = sample.student_id
        if sid not in per_student or distance < per_student[sid][0]:
            per_student[sid] = (distance, sample.student)
    distance, student = min(per_student.values(), key=lambda pair: pair[0])
    if distance > Config.COSINE_THRESHOLD:
        return {'label': 'unknown', 'message': 'Unknown', 'distance': round(distance, 4)}
    return {'label': 'matched', 'student_id': student.id,
            'name': student.full_name, 'code': student.code,
            'distance': round(distance, 4),
            'similarity': round(max(0.0, min(1.0, 1.0 - distance)) * 100, 2),
            'antispoof_score': liveness.get('antispoof_score') if liveness else None}
