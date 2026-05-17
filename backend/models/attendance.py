from extensions import db
import uuid
from datetime import datetime

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    join_time = db.Column(db.DateTime, default=datetime.utcnow)
    leave_time = db.Column(db.DateTime)
    total_duration_seconds = db.Column(db.Integer)
    face_check_passed = db.Column(db.Boolean)
    status = db.Column(db.String(20), default='present')
