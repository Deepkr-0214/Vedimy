from extensions import db
import uuid
from datetime import datetime

class Violation(db.Model):
    __tablename__ = 'violations'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    exam_id = db.Column(db.String(36), db.ForeignKey('exams.id'))
    room_id = db.Column(db.String(36), db.ForeignKey('rooms.id'))
    violation_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), default='warning')
    screenshot_path = db.Column(db.String(500))
    auto_action = db.Column(db.String(50))
    warning_count = db.Column(db.Integer, default=1)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
