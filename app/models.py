from . import db
from flask_login import UserMixin
from passlib.hash import pbkdf2_sha256 as sha256
from datetime import datetime
import json

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(200), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin','teacher','student'
    full_name = db.Column(db.String(200))
    points = db.Column(db.Integer, default=0)
    badges = db.Column(db.String(500), default="[]")  # JSON list
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # in User model add columns
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    streak = db.Column(db.Integer, default=0)   # consecutive days activity (optional)
    last_active = db.Column(db.DateTime)
    class_year = db.Column(db.String(50), nullable=True)   # e.g. 'CSE-3' or '2024'
    semester = db.Column(db.String(20), nullable=True)

    def verify_password(self, password):
        return sha256.verify(password, self.password_hash)

    @staticmethod
    def hash_password(password):
        return sha256.hash(password)

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    teacher = db.relationship('User', backref='subjects')
    class_year = db.Column(db.String(50), nullable=True)
    semester = db.Column(db.String(20), nullable=True)

class Assessment(db.Model):
    __tablename__ = 'assessments'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    subject = db.relationship('Subject', backref='assessments')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'))
    assessment = db.relationship('Assessment', backref='questions')
    text = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, nullable=False)  # JSON list of options
    correct_index = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(200), nullable=False)  # important for analysis

class StudentAssessmentAttempt(db.Model):
    __tablename__ = 'attempts'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    student = db.relationship('User', backref='attempts')
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'))
    assessment = db.relationship('Assessment')
    answers_json = db.Column(db.Text)  # JSON mapping question_id -> chosen_index
    score = db.Column(db.Float)
    completed = db.Column(db.Boolean, default=False)
    watched_video_for_weak_topic = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'), nullable=False)

class TopicVideo(db.Model):
    __tablename__ = 'topic_videos'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), unique=True)
    youtube_url = db.Column(db.String(500))
