"""
Evaluate face recognition using a folder structure:

data/test/
    StudentA/
        001.jpg
        002.jpg
    StudentB/
        001.jpg
        002.jpg

The script compares each test image with enrolled embeddings in the database.

Usage:
    python evaluation/evaluate.py

Optional environment variables:
    RECOGNITION_THRESHOLD=0.50
"""

import csv
import sys
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.database import SessionLocal, init_db
from database.models import Student, FaceEmbedding
from recognition.encoder import get_single_embedding
from recognition.matcher import deserialize_embedding, cosine_similarity

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

def load_gallery(db):
    rows = db.execute(
        select(FaceEmbedding, Student)
        .join(Student, FaceEmbedding.student_id == Student.id)
    ).all()

    gallery = []
    for face_embedding, student in rows:
        gallery.append(
            (student, deserialize_embedding(face_embedding.embedding))
        )
    return gallery

def predict(embedding, gallery):
    best_student = None
    best_score = -1.0

    for student, stored in gallery:
        score = cosine_similarity(embedding, stored)
        if score > best_score:
            best_score = score
            best_student = student

    return best_student, best_score

def main():
    init_db()
    test_root = ROOT / "data" / "test"

    if not test_root.exists():
        print("Không tìm thấy data/test.")
        return

    with SessionLocal() as db:
        gallery = load_gallery(db)

        if not gallery:
            print("Database chưa có enrollment.")
            return

        rows = []

        for person_dir in sorted(test_root.iterdir()):
            if not person_dir.is_dir():
                continue

            expected = person_dir.name

            for image_path in sorted(person_dir.iterdir()):
                if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                image = cv2.imread(str(image_path))
                if image is None:
                    continue

                try:
                    embedding, _ = get_single_embedding(image)
                    predicted, score = predict(embedding, gallery)

                    predicted_code = predicted.student_code if predicted else "Unknown"
                    predicted_name = predicted.full_name if predicted else "Unknown"

                    rows.append({
                        "file": str(image_path.relative_to(ROOT)),
                        "expected": expected,
                        "predicted": predicted_code,
                        "predicted_name": predicted_name,
                        "similarity": round(score, 6),
                        "correct": expected == predicted_code,
                    })

                except Exception as exc:
                    rows.append({
                        "file": str(image_path.relative_to(ROOT)),
                        "expected": expected,
                        "predicted": "ERROR",
                        "predicted_name": str(exc),
                        "similarity": "",
                        "correct": False,
                    })

        output = ROOT / "evaluation" / "results.csv"
        with output.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "file",
                    "expected",
                    "predicted",
                    "predicted_name",
                    "similarity",
                    "correct",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        valid = [r for r in rows if r["predicted"] != "ERROR"]

        if not valid:
            print("Không có kết quả hợp lệ.")
            return

        accuracy = sum(r["correct"] for r in valid) / len(valid) * 100

        print(f"Số ảnh test: {len(valid)}")
        print(f"Accuracy: {accuracy:.2f}%")
        print(f"Chi tiết: {output}")

if __name__ == "__main__":
    main()
