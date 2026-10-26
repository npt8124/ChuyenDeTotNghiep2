import base64
import json
import os
import uuid
import unicodedata
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from config import Config
from models import db, User, SchoolClass, Student, FaceSample, Session, Attendance

app = Flask(__name__)
app.config.from_object(Config)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

@app.context_processor
def common():
    return {'now': datetime.now}

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.first():
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if len(username) < 3 or len(password) < 10:
            flash('Tên đăng nhập tối thiểu 3 ký tự; mật khẩu tối thiểu 10 ký tự.', 'danger')
        else:
            db.session.add(User(username=username, password_hash=generate_password_hash(password)))
            db.session.commit()
            flash('Đã tạo tài khoản. Hãy đăng nhập.', 'success')
            return redirect(url_for('login'))
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not User.query.first():
        return redirect(url_for('setup'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username', '')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password', '')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Sai tên đăng nhập hoặc mật khẩu.', 'danger')
    return render_template('login.html')

@app.post('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.get('/')
@login_required
def dashboard():
    sessions = Session.query.order_by(Session.id.desc()).limit(10).all()
    return render_template('dashboard.html', sessions=sessions,
        count_students=Student.query.count(), count_classes=SchoolClass.query.count(),
        count_faces=FaceSample.query.count())

@app.route('/classes', methods=['GET', 'POST'])
@login_required
def classes():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        if not code or not name:
            flash('Nhập đủ mã và tên lớp.', 'danger')
        else:
            try:
                db.session.add(SchoolClass(code=code, name=name))
                db.session.commit()
                flash('Đã thêm lớp.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash('Mã lớp đã tồn tại.', 'danger')
        return redirect(url_for('classes'))
    return render_template('classes.html', classes=SchoolClass.query.order_by(SchoolClass.code).all())

@app.route('/students', methods=['GET', 'POST'])
@login_required
def students():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        class_id = request.form.get('class_id', type=int)
        if not code or not name or not db.session.get(SchoolClass, class_id):
            flash('Dữ liệu sinh viên không hợp lệ.', 'danger')
        else:
            try:
                db.session.add(Student(code=code, full_name=name, class_id=class_id))
                db.session.commit()
                flash('Đã thêm sinh viên.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash('Mã sinh viên đã tồn tại.', 'danger')
        return redirect(url_for('students'))
    return render_template('students.html', students=Student.query.order_by(Student.id.desc()).all(), classes=SchoolClass.query.all())

@app.route('/students/<int:student_id>/faces', methods=['GET', 'POST'])
@login_required
def enroll(student_id):
    student = db.get_or_404(Student, student_id)
    if request.method == 'POST':
        file = request.files.get('image')
        if not file or not file.filename:
            flash('Chọn một ảnh JPG/PNG.', 'danger')
            return redirect(url_for('enroll', student_id=student_id))
        if Path(secure_filename(file.filename)).suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            flash('Chỉ nhận JPG/PNG.', 'danger')
            return redirect(url_for('enroll', student_id=student_id))
        raw = file.read()
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None or image.shape[0] < 80 or image.shape[1] < 80:
            flash('Ảnh không hợp lệ hoặc quá nhỏ.', 'danger')
            return redirect(url_for('enroll', student_id=student_id))
        try:
            from recognition import encode_one
            embedding = encode_one(image)
        except Exception as exc:
            flash('Không đăng ký được khuôn mặt: ' + str(exc), 'danger')
            return redirect(url_for('enroll', student_id=student_id))
        filename = f'{student.id}_{uuid.uuid4().hex}.jpg'
        path = Path(app.config['UPLOAD_FOLDER']) / filename
        cv2.imwrite(str(path), image)
        db.session.add(FaceSample(student_id=student.id, image_path=filename, embedding_json=json.dumps(embedding)))
        db.session.commit()
        flash('Đăng ký khuôn mặt thành công.', 'success')
        return redirect(url_for('enroll', student_id=student_id))
    return render_template('enroll.html', student=student)

@app.post('/api/students/<int:student_id>/faces/camera')
@login_required
def enroll_camera(student_id):
    student = db.get_or_404(Student, student_id)
    data = request.get_json(silent=True) or {}
    encoded = data.get('image')
    if not isinstance(encoded, str) or not encoded.startswith('data:image/jpeg;base64,'):
        return jsonify(error='Ảnh camera không hợp lệ.'), 400
    try:
        raw = base64.b64decode(encoded.split(',', 1)[1], validate=True)
        if len(raw) > 6 * 1024 * 1024:
            return jsonify(error='Ảnh quá lớn.'), 413
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or min(image.shape[:2]) < 80:
            return jsonify(error='Không đọc được ảnh camera.'), 400
        from recognition import encode_one
        embedding = encode_one(image)
    except (ValueError, Exception) as exc:
        return jsonify(error='Không đăng ký được khuôn mặt: ' + str(exc)), 400
    filename = f'{student.id}_{uuid.uuid4().hex}.jpg'
    path = Path(app.config['UPLOAD_FOLDER']) / filename
    if not cv2.imwrite(str(path), image):
        return jsonify(error='Không lưu được ảnh.'), 500
    try:
        db.session.add(FaceSample(student_id=student.id, image_path=filename,
                                  embedding_json=json.dumps(embedding)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        path.unlink(missing_ok=True)
        return jsonify(error='Không lưu được dữ liệu vào database.'), 500
    return jsonify(message='Đã lưu ảnh camera và embedding.', total=len(student.faces))

@app.post('/faces/<int:face_id>/delete')
@login_required
def delete_face(face_id):
    face = db.get_or_404(FaceSample, face_id)
    student_id = face.student_id
    path = Path(app.config['UPLOAD_FOLDER']) / face.image_path
    db.session.delete(face)
    db.session.commit()
    path.unlink(missing_ok=True)
    flash('Đã xóa ảnh và embedding.', 'success')
    return redirect(url_for('enroll', student_id=student_id))

@app.route('/sessions', methods=['GET', 'POST'])
@login_required
def sessions():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        class_id = request.form.get('class_id', type=int)
        if title and db.session.get(SchoolClass, class_id):
            new_session = Session(title=title, class_id=class_id)
            db.session.add(new_session)
            db.session.flush()
            enrolled_students = Student.query.filter_by(class_id=class_id).all()
            for student in enrolled_students:
                db.session.add(Attendance(
                    session_id=new_session.id, student_id=student.id,
                    status='absent', recorded_at=datetime.now()
                ))
            db.session.commit()
            flash('Đã tạo buổi điểm danh.', 'success')
        else:
            flash('Chọn lớp và nhập tên buổi.', 'danger')
        return redirect(url_for('sessions'))
    return render_template('sessions.html', sessions=Session.query.order_by(Session.id.desc()).all(), classes=SchoolClass.query.all())

@app.post('/sessions/<int:session_id>/close')
@login_required
def close_session(session_id):
    s = db.get_or_404(Session, session_id)
    if not s.ended_at:
        s.ended_at = datetime.now()
        db.session.commit()
    return redirect(url_for('session_detail', session_id=session_id))

@app.get('/sessions/<int:session_id>')
@login_required
def session_detail(session_id):
    s = db.get_or_404(Session, session_id)
    rows = Attendance.query.filter_by(session_id=session_id).all()
    students = Student.query.filter_by(class_id=s.class_id).all()
    attendance_by_student = {a.student_id: a for a in rows}
    # Nhóm theo trạng thái trước, rồi tên gọi -> tên đệm -> họ (A-Z).
    rank = {'present': 0, 'late': 1, 'absent': 2}
    def normalize(text):
        text = unicodedata.normalize('NFD', text.casefold())
        return ''.join(c for c in text if unicodedata.category(c) != 'Mn').replace('đ', 'd')
    def student_key(student):
        words = normalize(student.full_name.strip()).split()
        name = words[-1] if words else ''
        middle = ' '.join(words[1:-1]) if len(words) > 2 else ''
        surname = words[0] if len(words) > 1 else ''
        a = attendance_by_student.get(student.id)
        status = a.status if a else 'absent'
        return (rank.get(status, 3), name, middle, surname, normalize(student.code))
    students.sort(key=student_key)
    return render_template('session_detail.html', session=s, students=students, attendance=attendance_by_student)

@app.post('/sessions/<int:session_id>/attendance/<int:student_id>')
@login_required
def edit_attendance(session_id, student_id):
    s = db.get_or_404(Session, session_id)
    student = db.get_or_404(Student, student_id)
    if student.class_id != s.class_id:
        abort(400)
    status = request.form.get('status')
    if status not in ('present', 'late', 'absent'):
        abort(400)
    a = Attendance.query.filter_by(session_id=s.id, student_id=student.id).first()
    if not a:
        a = Attendance(session_id=s.id, student_id=student.id)
        db.session.add(a)
    a.status = status
    a.note = request.form.get('note', '')[:255]
    a.recorded_at = datetime.now()
    db.session.commit()
    flash('Đã cập nhật điểm danh.', 'success')
    return redirect(url_for('session_detail', session_id=session_id))

@app.get('/sessions/<int:session_id>/camera')
@login_required
def camera(session_id):
    s = db.get_or_404(Session, session_id)
    if s.ended_at:
        flash('Buổi điểm danh đã kết thúc.', 'danger')
        return redirect(url_for('session_detail', session_id=session_id))
    return render_template('camera.html', session=s)

@app.post('/api/sessions/<int:session_id>/recognize')
@login_required
def recognize_api(session_id):
    s = db.get_or_404(Session, session_id)
    if s.ended_at:
        return jsonify(error='Buổi điểm danh đã kết thúc.'), 409
    data = request.get_json(silent=True) or {}
    encoded = data.get('image', '')
    try:
        if not isinstance(encoded, str) or not encoded.startswith('data:image/jpeg;base64,'):
            raise ValueError('Dữ liệu ảnh không hợp lệ.')
        raw = base64.b64decode(encoded.split(',', 1)[1], validate=True)
        if len(raw) > 2_000_000:
            raise ValueError('Ảnh vượt giới hạn.')
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('Không đọc được ảnh.')
        from recognition import recognize
        result = recognize(image, s.class_id)
        if result.get('label') != 'matched':
            return jsonify(result)
        student_id = result['student_id']
        record = Attendance.query.filter_by(session_id=s.id, student_id=student_id).first()
        if record and record.status in ('present', 'late'):
            result['attendance'] = 'already_recorded'
            return jsonify(result)
        if record is None:
            record = Attendance(session_id=s.id, student_id=student_id, status='present')
            db.session.add(record)
        else:
            record.status = 'present'
        record.recorded_at = datetime.now()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            result['attendance'] = 'already_recorded'
        else:
            result['attendance'] = 'recorded'
        return jsonify(result)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception:
        app.logger.exception('Recognition failed')
        return jsonify(error='Không thể xử lý ảnh. Kiểm tra log máy chủ.'), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
