import base64
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import select

from database.database import SessionLocal
from database.models import Student, FaceEmbedding
from recognition.encoder import image_bytes_to_bgr, get_single_embedding
from recognition.matcher import serialize_embedding

students_bp = Blueprint("students", __name__)

def _student_dict(student):
    return {
        "id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "class_name": student.class_name,
        "email": student.email,
        "created_at": student.created_at.isoformat() if student.created_at else None,
        "has_face": len(student.face_embeddings) > 0,
    }

@students_bp.get("/students")
def students_page():
    return render_template("students.html")

@students_bp.get("/enrollment")
def enrollment_page():
    return render_template("enrollment.html")

@students_bp.get("/api/students")
def list_students():
    with SessionLocal() as db:
        students = db.scalars(select(Student).order_by(Student.id.desc())).all()
        return jsonify([_student_dict(s) for s in students])

@students_bp.post("/api/students")
def create_student():
    data = request.get_json(silent=True) or {}

    code = str(data.get("student_code", "")).strip()
    name = str(data.get("full_name", "")).strip()
    class_name = str(data.get("class_name", "")).strip()
    email = str(data.get("email", "")).strip() or None

    if not code or not name or not class_name:
        return jsonify({"error": "MSSV, họ tên và lớp là bắt buộc."}), 400

    with SessionLocal() as db:
        exists = db.scalar(select(Student).where(Student.student_code == code))
        if exists:
            return jsonify({"error": "MSSV đã tồn tại."}), 409

        student = Student(
            student_code=code,
            full_name=name,
            class_name=class_name,
            email=email,
        )
        db.add(student)
        db.commit()
        db.refresh(student)

        return jsonify(_student_dict(student)), 201

@students_bp.put("/api/students/<int:student_id>")
def update_student(student_id):
    data = request.get_json(silent=True) or {}

    with SessionLocal() as db:
        student = db.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy sinh viên."}), 404

        student.student_code = str(data.get("student_code", student.student_code)).strip()
        student.full_name = str(data.get("full_name", student.full_name)).strip()
        student.class_name = str(data.get("class_name", student.class_name)).strip()
        student.email = str(data.get("email", student.email or "")).strip() or None

        db.commit()
        db.refresh(student)
        return jsonify(_student_dict(student))

@students_bp.delete("/api/students/<int:student_id>")
def delete_student(student_id):
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy sinh viên."}), 404

        db.delete(student)
        db.commit()
        return jsonify({"message": "Đã xóa sinh viên."})

@students_bp.post("/api/enrollment")
def enroll_face():
    data = request.get_json(silent=True) or {}

    try:
        student_id = int(data.get("student_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "student_id không hợp lệ."}), 400

    image_data = data.get("image")
    if not image_data:
        return jsonify({"error": "Thiếu ảnh khuôn mặt."}), 400

    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        image_bytes = base64.b64decode(image_data)
        image_bgr = image_bytes_to_bgr(image_bytes)
        embedding, face = get_single_embedding(image_bgr)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    with SessionLocal() as db:
        student = db.get(Student, student_id)
        if not student:
            return jsonify({"error": "Không tìm thấy sinh viên."}), 404

        # Replace the previous enrollment for this demo.
        for old in list(student.face_embeddings):
            db.delete(old)

        record = FaceEmbedding(
            student_id=student.id,
            embedding=serialize_embedding(embedding),
            created_at=datetime.now(),
        )
        db.add(record)
        db.commit()

        return jsonify({
            "message": "Đăng ký khuôn mặt thành công.",
            "student": _student_dict(student),
            "embedding_dimension": int(embedding.shape[0]),
            "face_bbox": [float(x) for x in face.bbox],
        })
