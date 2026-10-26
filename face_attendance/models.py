from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class SchoolClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    students = db.relationship('Student', back_populates='school_class')

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False)
    school_class = db.relationship('SchoolClass', back_populates='students')
    faces = db.relationship('FaceSample', cascade='all, delete-orphan', back_populates='student')

class FaceSample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    image_path = db.Column(db.String(300), nullable=False)
    embedding_json = db.Column(db.Text, nullable=False)
    student = db.relationship('Student', back_populates='faces')

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    ended_at = db.Column(db.DateTime)
    school_class = db.relationship('SchoolClass')

class Attendance(db.Model):
    __table_args__ = (UniqueConstraint('session_id', 'student_id', name='uq_session_student'),)
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    status = db.Column(db.String(20), default='absent', nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    note = db.Column(db.String(255), default='')
    session = db.relationship('Session')
    student = db.relationship('Student')
