from datetime import datetime
from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import select

from database.database import SessionLocal
from database.models import Session as AttendanceSession

sessions_bp = Blueprint("sessions", __name__)

@sessions_bp.get("/api/sessions")
def list_sessions():
    with SessionLocal() as db:
        rows = db.scalars(
            select(AttendanceSession).order_by(AttendanceSession.id.desc())
        ).all()

        return jsonify([
            {
                "id": row.id,
                "class_name": row.class_name,
                "session_date": row.session_date,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "status": row.status,
            }
            for row in rows
        ])

@sessions_bp.post("/api/sessions")
def create_session():
    data = request.get_json(silent=True) or {}

    class_name = str(data.get("class_name", "")).strip()
    session_date = str(data.get("session_date", "")).strip()
    start_time = str(data.get("start_time", "")).strip()
    end_time = str(data.get("end_time", "")).strip() or None

    if not class_name or not session_date or not start_time:
        return jsonify({"error": "Lớp, ngày và giờ bắt đầu là bắt buộc."}), 400

    with SessionLocal() as db:
        row = AttendanceSession(
            class_name=class_name,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            status="active",
            created_at=datetime.now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        return jsonify({
            "id": row.id,
            "class_name": row.class_name,
            "session_date": row.session_date,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "status": row.status,
        }), 201

@sessions_bp.put("/api/sessions/<int:session_id>/close")
def close_session(session_id):
    with SessionLocal() as db:
        row = db.get(AttendanceSession, session_id)
        if not row:
            return jsonify({"error": "Không tìm thấy buổi học."}), 404

        row.status = "closed"
        row.end_time = datetime.now().strftime("%H:%M")
        db.commit()

        return jsonify({"message": "Đã đóng buổi học.", "status": row.status})
