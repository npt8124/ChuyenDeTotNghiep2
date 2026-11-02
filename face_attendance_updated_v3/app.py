import base64
import json
import os
import uuid
import unicodedata
import csv
import io
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort, session as flask_session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
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
    # Additive SQLite migration: preserve existing attendance records.
    columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(attendance)"))}
    if 'match_distance' not in columns:
        db.session.execute(text("ALTER TABLE attendance ADD COLUMN match_distance FLOAT"))
        db.session.commit()

PREVIEW_DIR = Path(app.instance_path) / 'import_previews'
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def _save_image_unicode_safe(image, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    extension = path.suffix.lower() or '.jpg'
    success, buffer = cv2.imencode(extension, image)
    if not success or buffer is None:
        raise OSError(f'OpenCV không mã hóa được ảnh với định dạng {extension}.')
    written = path.write_bytes(buffer.tobytes())
    if written <= 0 or not path.is_file():
        raise OSError('Không ghi được dữ liệu ảnh xuống ổ đĩa.')
    return path


def _normalize_header(value):
    value = unicodedata.normalize('NFD', str(value or '').strip().casefold())
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    return value.replace('đ', 'd').replace('_', '').replace(' ', '')


def _read_student_file(file_storage):
    filename = secure_filename(file_storage.filename or '')
    suffix = Path(filename).suffix.lower()
    raw = file_storage.read()
    if not raw:
        raise ValueError('File không có dữ liệu.')
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('File vượt giới hạn 5 MB.')
    if suffix == '.xlsx':
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ValueError('Thiếu openpyxl. Chạy: python -m pip install openpyxl') from exc
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        headers = next(iterator, None)
        if not headers:
            raise ValueError('File Excel không có dòng tiêu đề.')
        records = list(iterator)
        workbook.close()
    elif suffix == '.csv':
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                content = raw.decode('cp1258')
            except UnicodeDecodeError as exc:
                raise ValueError('Không đọc được mã hóa CSV. Hãy lưu file dưới dạng UTF-8.') from exc
        sample = content[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(content), dialect)
        headers = next(reader, None)
        if not headers:
            raise ValueError('File CSV không có dòng tiêu đề.')
        records = list(reader)
    else:
        raise ValueError('Chỉ hỗ trợ file .xlsx hoặc .csv.')

    header_map = {_normalize_header(value): index for index, value in enumerate(headers)}
    code_index = next((header_map[k] for k in ('mssv', 'masinhvien') if k in header_map), None)
    name_index = next((header_map[k] for k in ('hoten', 'hovaten', 'fullname') if k in header_map), None)
    if code_index is None or name_index is None:
        raise ValueError('File phải có hai cột tiêu đề MSSV và Họ tên.')

    rows = []
    for line_no, record in enumerate(records, start=2):
        code = str(record[code_index] if code_index < len(record) and record[code_index] is not None else '').strip()
        name = str(record[name_index] if name_index < len(record) and record[name_index] is not None else '').strip()
        # Excel may store numeric student codes as floats.
        if code.endswith('.0') and code[:-2].isdigit():
            code = code[:-2]
        if not code and not name:
            continue
        errors = []
        if not code:
            errors.append('Thiếu MSSV')
        if not name:
            errors.append('Thiếu họ tên')
        if len(code) > 30:
            errors.append('MSSV quá 30 ký tự')
        if len(name) > 150:
            errors.append('Họ tên quá 150 ký tự')
        rows.append({'line': line_no, 'code': code, 'name': name, 'errors': errors})
    if not rows:
        raise ValueError('Không tìm thấy dòng sinh viên trong file.')
    return rows

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

def _vietnamese_word_sort_key(word):
    """Vietnamese alphabetical key, preserving letter variants and tone marks."""
    alphabet = {
        'a': 0, 'ă': 1, 'â': 2, 'b': 3, 'c': 4, 'd': 5, 'đ': 6,
        'e': 7, 'ê': 8, 'g': 9, 'h': 10, 'i': 11, 'k': 12, 'l': 13,
        'm': 14, 'n': 15, 'o': 16, 'ô': 17, 'ơ': 18, 'p': 19,
        'q': 20, 'r': 21, 's': 22, 't': 23, 'u': 24, 'ư': 25,
        'v': 26, 'x': 27, 'y': 28,
    }
    tone_order = {'': 0, '\u0300': 1, '\u0309': 2, '\u0303': 3,
                  '\u0301': 4, '\u0323': 5}
    shape_marks = {'\u0306': 1, '\u0302': 2, '\u031b': 3}
    result = []
    for char in word.casefold():
        if char.isspace():
            continue
        if char == 'đ':
            result.append((alphabet['đ'], 0, 0))
            continue
        decomposed = unicodedata.normalize('NFD', char)
        base = decomposed[0]
        marks = decomposed[1:]
        # The alphabet order already distinguishes ă/â, ê, ô/ơ and ư.
        letter_index = alphabet.get(base, 100 + ord(base))
        tone = next((mark for mark in marks if mark in tone_order), '')
        result.append((letter_index, tone_order[tone], 0))
    return tuple(result)


def _student_name_sort_key(student):
    """Sort Vietnamese full names right-to-left: given name, middle name, surname."""
    words = (student.full_name or '').strip().split()
    # Compare the final word first, then each preceding word moving right-to-left.
    name_parts = tuple(_vietnamese_word_sort_key(word) for word in reversed(words))
    return (name_parts, (student.code or '').casefold())


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
    student_rows = Student.query.all()
    student_rows.sort(key=_student_name_sort_key)
    return render_template('students.html', students=student_rows, classes=SchoolClass.query.order_by(SchoolClass.code).all())


@app.post('/students/<int:student_id>/delete')
@login_required
def delete_student(student_id):
    student = db.get_or_404(Student, student_id)

    # Collect registered face image paths before deleting related database rows.
    face_paths = [
        Path(app.config['UPLOAD_FOLDER']) / Path(face.image_path).name
        for face in student.faces
    ]

    try:
        # A student may appear in past attendance sessions. Remove those rows
        # explicitly because Attendance.student_id is a non-null foreign key.
        Attendance.query.filter_by(student_id=student.id).delete(synchronize_session=False)
        db.session.delete(student)  # FaceSample rows are cascade-deleted by relationship.
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('Could not delete student %s', student_id)
        flash('Không thể xóa sinh viên. Vui lòng kiểm tra log máy chủ.', 'danger')
        return redirect(url_for('students'))

    for face_path in face_paths:
        try:
            face_path.unlink(missing_ok=True)
        except OSError:
            app.logger.exception('Could not remove face image %s', face_path)

    flash('Đã xóa sinh viên cùng ảnh khuôn mặt và các bản ghi điểm danh liên quan.', 'success')
    return redirect(url_for('students'))


@app.post('/students/import/preview')
@login_required
def students_import_preview():
    class_id = request.form.get('class_id', type=int)
    school_class = db.session.get(SchoolClass, class_id)
    uploaded = request.files.get('file')
    if not school_class or not uploaded or not uploaded.filename:
        flash('Hãy chọn lớp và file Excel/CSV.', 'danger')
        return redirect(url_for('students'))
    try:
        rows = _read_student_file(uploaded)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('students'))

    existing = {code for (code,) in db.session.query(Student.code).all()}
    seen = set()
    for row in rows:
        if row['code'] and row['code'] in existing:
            row['errors'].append('MSSV đã tồn tại trong hệ thống')
        if row['code'] and row['code'] in seen:
            row['errors'].append('MSSV bị lặp trong file')
        if row['code']:
            seen.add(row['code'])
    token = uuid.uuid4().hex
    preview_path = PREVIEW_DIR / f'{token}.json'
    preview_path.write_text(json.dumps({'class_id': class_id, 'rows': rows}, ensure_ascii=False), encoding='utf-8')
    flask_session['student_import_token'] = token
    return render_template('student_import_preview.html', school_class=school_class, rows=rows,
                           valid_count=sum(not row['errors'] for row in rows), token=token)


@app.post('/students/import/confirm')
@login_required
def students_import_confirm():
    token = request.form.get('token', '')
    if not token or token != flask_session.get('student_import_token') or not token.isalnum():
        abort(400)
    preview_path = PREVIEW_DIR / f'{token}.json'
    if not preview_path.is_file():
        abort(400)
    payload = json.loads(preview_path.read_text(encoding='utf-8'))
    school_class = db.session.get(SchoolClass, payload.get('class_id'))
    if not school_class:
        abort(400)
    existing = {code for (code,) in db.session.query(Student.code).all()}
    imported = skipped = 0
    try:
        for row in payload['rows']:
            if row['errors'] or not row['code'] or row['code'] in existing:
                skipped += 1
                continue
            db.session.add(Student(code=row['code'], full_name=row['name'], class_id=school_class.id))
            existing.add(row['code'])
            imported += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('Student import failed')
        flash('Có lỗi khi nhập dữ liệu; database đã rollback.', 'danger')
    else:
        flash(f'Nhập thành công {imported} sinh viên; bỏ qua {skipped} dòng không hợp lệ hoặc trùng MSSV.', 'success')
    finally:
        preview_path.unlink(missing_ok=True)
        flask_session.pop('student_import_token', None)
    return redirect(url_for('students'))


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
        try:
            _save_image_unicode_safe(image, path)
            db.session.add(FaceSample(student_id=student.id, image_path=filename,
                                      embedding_json=json.dumps(embedding)))
            db.session.commit()
        except Exception:
            db.session.rollback()
            path.unlink(missing_ok=True)
            app.logger.exception('Không lưu được ảnh khuôn mặt upload cho student_id=%s', student.id)
            flash('Không lưu được ảnh hoặc dữ liệu khuôn mặt. Kiểm tra quyền ghi thư mục uploads/faces và log máy chủ.', 'danger')
            return redirect(url_for('enroll', student_id=student_id))
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
    try:
        _save_image_unicode_safe(image, path)
    except Exception:
        path.unlink(missing_ok=True)
        app.logger.exception('Không lưu được file ảnh camera cho student_id=%s tại %s',
                             student.id, path)
        return jsonify(error=(
            'Không ghi được file ảnh vào thư mục lưu trữ. '
            'Kiểm tra thư mục uploads/faces, quyền ghi và log terminal.'
        )), 500
    try:
        db.session.add(FaceSample(student_id=student.id, image_path=filename,
                                  embedding_json=json.dumps(embedding)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        path.unlink(missing_ok=True)
        app.logger.exception('Không lưu được FaceSample vào SQLite cho student_id=%s', student.id)
        return jsonify(error='Ảnh đã được tạo nhưng không lưu được dữ liệu vào database. Kiểm tra log máy chủ.'), 500
    return jsonify(message='Đã lưu ảnh camera.', total=len(student.faces))

@app.post('/faces/<int:face_id>/delete')
@login_required
def delete_face(face_id):
    face = db.get_or_404(FaceSample, face_id)
    student_id = face.student_id
    path = Path(app.config['UPLOAD_FOLDER']) / face.image_path
    db.session.delete(face)
    db.session.commit()
    path.unlink(missing_ok=True)
    flash('Đã xóa ảnh.', 'success')
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
    # Nhóm theo trạng thái trước; trong từng nhóm sắp tên theo quy tắc Việt
    # từ phải sang trái: tên gọi, các từ đệm, sau cùng là họ.
    rank = {'present': 0, 'late': 1, 'absent': 2}
    def student_key(student):
        a = attendance_by_student.get(student.id)
        status = a.status if a else 'absent'
        return (rank.get(status, 3), _student_name_sort_key(student))
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
    a.match_distance = None
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
        # Anti-spoofing is enabled only for the live attendance camera.
        result = recognize(image, s.class_id, anti_spoofing=True)
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
        record.match_distance = result.get('distance')
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
