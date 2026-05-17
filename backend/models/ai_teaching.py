from extensions import db
import uuid
from datetime import datetime

class LectureRecord(db.Model):
    __tablename__ = 'lecture_records'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'), nullable=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    title = db.Column(db.String(255))
    transcript = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(20), default='recording')
    original_filename = db.Column(db.String(255))
    duration_seconds = db.Column(db.Integer)
    word_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AILecture(db.Model):
    __tablename__ = 'ai_lectures'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lecture_id = db.Column(db.String(36), db.ForeignKey('lecture_records.id'))
    summary = db.Column(db.Text)
    key_points = db.Column(db.Text)       # JSON string
    important_topics = db.Column(db.Text) # JSON string
    keywords = db.Column(db.Text)         # JSON string
    language = db.Column(db.String(10), default='en')
    processing_status = db.Column(db.String(20), default='pending')
    processing_time_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AITranslation(db.Model):
    __tablename__ = 'ai_translations'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ai_lecture_id = db.Column(db.String(36), db.ForeignKey('ai_lectures.id'))
    target_language = db.Column(db.String(10), nullable=False)
    translated_summary = db.Column(db.Text)
    translated_key_points = db.Column(db.Text) # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('ai_lecture_id', 'target_language'),)

class AIQuestion(db.Model):
    __tablename__ = 'ai_questions'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lecture_id = db.Column(db.String(36), db.ForeignKey('lecture_records.id'))
    ai_lecture_id = db.Column(db.String(36), db.ForeignKey('ai_lectures.id'))
    question_type = db.Column(db.String(20), nullable=False)
    question_count = db.Column(db.Integer, nullable=False)
    questions_json = db.Column(db.Text, nullable=False) # JSON string
    difficulty = db.Column(db.String(20), default='medium')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
