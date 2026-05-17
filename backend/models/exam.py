from extensions import db
import uuid
from datetime import datetime

class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    host_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    max_warnings = db.Column(db.Integer, default=3)
    face_check_interval = db.Column(db.Integer, default=10)
    instructions = db.Column(db.Text, nullable=True)
    questions_json = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), default='scheduled')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
