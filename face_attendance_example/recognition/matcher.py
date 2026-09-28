import json
import numpy as np
from config import RECOGNITION_THRESHOLD

def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)

def serialize_embedding(embedding):
    return json.dumps(np.asarray(embedding, dtype=np.float32).tolist())

def deserialize_embedding(value):
    return np.asarray(json.loads(value), dtype=np.float32)

def find_best_match(query_embedding, stored_embeddings):
    """
    stored_embeddings:
        list of tuples: (student, embedding_vector)
    returns:
        (student, similarity) or (None, best_similarity)
    """
    best_student = None
    best_similarity = -1.0

    for student, embedding in stored_embeddings:
        score = cosine_similarity(query_embedding, embedding)
        if score > best_similarity:
            best_similarity = score
            best_student = student

    if best_student is not None and best_similarity >= RECOGNITION_THRESHOLD:
        return best_student, best_similarity

    return None, best_similarity
