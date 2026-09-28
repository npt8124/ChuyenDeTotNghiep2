from datetime import datetime
from sqlalchemy import select
from database.models import Attendance

def record_attendance(db, session_id, student_id, similarity):
    existing = db.scalar(
        select(Attendance).where(
            Attendance.session_id == session_id,
            Attendance.student_id == student_id,
        )
    )

    if existing:
        return existing, False

    record = Attendance(
        session_id=session_id,
        student_id=student_id,
        check_in_time=datetime.now(),
        status="Present",
        similarity=similarity,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return record, True
