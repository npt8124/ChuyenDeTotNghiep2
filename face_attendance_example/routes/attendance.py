import base64
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import select

from database.database import SessionLocal
from database.models import Student, FaceEmbedding, Attendance, Session as AttendanceSession
from recognition.encoder import image_bytes_to_bgr, get_faces_from_image
from recognition.matcher import deserialize_embedding, find_best_match
from recognition.attendance import record_attendance

attendance_bp = Blueprint("attendance", __name__)

@attendance_bp.get("/attendance")
def attendance_page():
    return render_template("attendance.html")

@attendance_bp.get("/history")
def history_page():
    return render_template("history.html")

def _load_embeddings(db, class_name=None):
    stmt = (
        select(FaceEmbedding, Student)
        .join(Student, FaceEmbedding.student_id == Student.id)
    )

    if class_name:
        stmt = stmt.where(Student.class_name == class_name)

    rows = db.execute(stmt).all()
    return [
        (student, deserialize_embedding(face_embedding.embedding))
        for face_embedding, student in rows
    ]

@attendance_bp.post("/api/recognize")
def recognize():
    data = request.get_json(silent=True) or {}
    image_data = data.get("image")

    if not image_data:
        return jsonify({"error": "Thiếu ảnh camera."}), 400

    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "session_id không hợp lệ."}), 400

    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(image_data)
        image_bgr = image_bytes_to_bgr(image_bytes)
        faces = get_faces_from_image(image_bgr)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    with SessionLocal() as db:
        session = db.get(AttendanceSession, session_id)
        if not session:
            return jsonify({"error": "Không tìm thấy buổi học."}), 404

        if session.status != "active":
            return jsonify({"error": "Buổi học đã đóng."}), 400

        stored = _load_embeddings(db, session.class_name)
        results = []

        for face in faces:
            embedding = getattr(face, "normed_embedding", None)
            if embedding is None:
                embedding = getattr(face, "embedding", None)

            if embedding is None:
                continue

            student, similarity = find_best_match(embedding, stored)

            bbox = [int(round(x)) for x in face.bbox]

            if student:
                attendance, created = record_attendance(
                    db,
                    session_id=session.id,
                    student_id=student.id,
                    similarity=similarity,
                )

                results.append({
                    "recognized": True,
                    "student_id": student.id,
                    "student_code": student.student_code,
                    "full_name": student.full_name,
                    "similarity": round(similarity, 4),
                    "status": attendance.status,
                    "already_present": not created,
                    "check_in_time": attendance.check_in_time.strftime("%H:%M:%S"),
                    "bbox": bbox,
                })
            else:
                results.append({
                    "recognized": False,
                    "student_id": None,
                    "student_code": None,
                    "full_name": "Unknown",
                    "similarity": round(max(similarity, 0.0), 4),
                    "status": "Unknown",
                    "already_present": False,
                    "check_in_time": None,
                    "bbox": bbox,
                })

        return jsonify({
            "session_id": session.id,
            "timestamp": datetime.now().isoformat(),
            "face_count": len(faces),
            "results": results,
        })

@attendance_bp.get("/api/attendance")
def list_attendance():
    session_id = request.args.get("session_id", type=int)
    class_name = request.args.get("class_name", type=str)
    date_value = request.args.get("date", type=str)

    with SessionLocal() as db:
        stmt = (
            select(Attendance, Student, AttendanceSession)
            .join(Student, Attendance.student_id == Student.id)
            .join(AttendanceSession, Attendance.session_id == AttendanceSession.id)
            .order_by(Attendance.check_in_time.desc())
        )

        if session_id:
            stmt = stmt.where(Attendance.session_id == session_id)
        if class_name:
            stmt = stmt.where(Student.class_name == class_name)
        if date_value:
            stmt = stmt.where(AttendanceSession.session_date == date_value)

        rows = db.execute(stmt).all()

        return jsonify([
            {
                "id": attendance.id,
                "session_id": session.id,
                "student_id": student.id,
                "student_code": student.student_code,
                "full_name": student.full_name,
                "class_name": student.class_name,
                "session_date": session.session_date,
                "check_in_time": attendance.check_in_time.strftime("%H:%M:%S"),
                "status": attendance.status,
                "similarity": attendance.similarity,
            }
            for attendance, student, session in rows
        ])

@attendance_bp.put("/api/attendance/<int:attendance_id>")
def update_attendance(attendance_id):
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip()

    if status not in {"Present", "Late", "Absent"}:
        return jsonify({"error": "Trạng thái không hợp lệ."}), 400

    with SessionLocal() as db:
        row = db.get(Attendance, attendance_id)
        if not row:
            return jsonify({"error": "Không tìm thấy bản ghi."}), 404

        row.status = status
        db.commit()

        return jsonify({"message": "Đã cập nhật trạng thái."})
