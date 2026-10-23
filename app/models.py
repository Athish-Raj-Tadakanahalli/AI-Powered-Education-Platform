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
    is_approved = db.Column(db.Boolean, default=True)
    approval_status = db.Column(db.String(20), default='approved')  # 'pending', 'approved', 'rejected'
    streak_freeze = db.Column(db.Integer, default=1)  # Shield against missed days

    @property
    def title(self):
        lvl = self.level or 1
        if lvl <= 3:
            return "Apprentice Engineer"
        elif lvl <= 7:
            return "Code Artisan"
        elif lvl <= 11:
            return "Algorithm Master"
        else:
            return "Cyber Grandmaster"

    @property
    def avatar_border_class(self):
        lvl = self.level or 1
        if lvl <= 3:
            return "border-2 border-slate-300 dark:border-slate-600 shadow-sm"
        elif lvl <= 7:
            return "border-2 border-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.45)] ring-2 ring-cyan-400/20"
        elif lvl <= 11:
            return "border-2 border-amber-400 shadow-[0_0_16px_rgba(251,191,36,0.55)] ring-2 ring-amber-400/30"
        else:
            return "border-2 border-purple-500 shadow-[0_0_20px_rgba(168,85,247,0.65)] ring-2 ring-purple-500/30"

    @property
    def is_daily_goal_met(self):
        if not self.last_active:
            return False
        return self.last_active.date() == datetime.utcnow().date()

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
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student = db.relationship('User', backref='attempts')
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'), nullable=False)
    assessment = db.relationship('Assessment')
    answers_json = db.Column(db.Text)  # JSON mapping question_id -> chosen_index
    score = db.Column(db.Float)
    completed = db.Column(db.Boolean, default=False)
    watched_video_for_weak_topic = db.Column(db.Boolean, default=False)
    remediation_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TopicVideo(db.Model):
    __tablename__ = 'topic_videos'
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), unique=True)
    youtube_url = db.Column(db.String(500))

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    student = db.relationship('User', foreign_keys=[student_id], backref='attendance_records')
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    subject = db.relationship('Subject', backref='attendance_records')
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # 'Present' or 'Absent'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_id', 'date', name='unique_student_subject_date'),
    )

class LearningMaterial(db.Model):
    __tablename__ = 'learning_materials'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(250), nullable=True)
    file_type = db.Column(db.String(50), nullable=False, default='text')  # pdf, image, text, doc, ppt, other
    external_url = db.Column(db.String(500), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    teacher = db.relationship('User', backref='learning_materials')
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    subject = db.relationship('Subject', backref='learning_materials')
    target_class = db.Column(db.String(100), nullable=True, default='All')  # e.g. 'CSE-3' or 'All'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


